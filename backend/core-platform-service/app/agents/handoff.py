"""
Phase 25: typed agent-to-agent result passing.

Before this, a downstream step's input was resolved with
`dep_step.result.get("result", dep_step.result)` -- an untyped dict shrug
(app/supervisor/planner.py). This module gives that handoff a contract:

1. `CAPABILITY_AGENT_MAP` -- moved here from app/supervisor/supervisor.py
   (Phase 24) so it has one source of truth reachable from
   app/supervisor/policies.py and app/supervisor/planner.py without a
   circular import through app/supervisor/supervisor.py (which itself
   imports planner.py).
2. `resolve_declared_type` -- walks a dotted path against a producer's
   *declared* Pydantic output model class (via `model_fields`, never by
   instantiating it), for plan-validation-time type checking.
3. `resolve_runtime_value` -- walks the same dotted path against a real
   value (dict or BaseModel instance) at execution time.
4. An explicit adapter registry for legitimate shape conversions where a
   producer's declared field type doesn't already satisfy a consumer's
   declared field type. Adapters are hand-written and registered by
   (producer_type, consumer_type) key -- there is no inferred or
   LLM-generated coercion, ever.
"""
import logging
from typing import Any, Callable, Optional, Union, get_args, get_origin

from pydantic import BaseModel

logger = logging.getLogger(__name__)


# Phase 24: capability -> registered-agent-name correspondence, verified
# against app/execution/contracts.py (see that module's docstring history
# for the reasoning on which capabilities are deliberately absent --
# text_generation, gmail.send, workgraph.create_task, digest.daily and
# database_report call runtime_service / the underlying services directly,
# never a registered Agent). Phase 25 reuses this same mapping as the
# producer/consumer schema lookup for typed input_bindings: a capability
# absent here has no declared Agent output/input schema to check against,
# so a plan step trying to bind against one is rejected at validation time.
CAPABILITY_AGENT_MAP: dict[str, str] = {
    "rag_search": "KnowledgeAgent",
    "rag_answer": "KnowledgeAgent",
    "database_query": "DataAgent",
    "document_summary": "DocumentAgent",
    "meeting.extract": "MeetingAgent",
    "inbox.classify": "InboxAgent",
    "inbox.draft_reply": "InboxAgent",
}


class PathResolutionError(ValueError):
    """Raised when a dotted path does not exist on a declared model, or a
    binding reference string is malformed."""


def unwrap_optional(tp: Any) -> Any:
    """Peels one layer of Optional[...]/Union[..., None] so a field
    declared as `Optional[SomeModel]` can still be walked into. Any other
    type (including list[...]/dict[...] generics) is returned unchanged --
    those are meaningful whole-field types for adapter/compatibility
    matching, not something to unwrap."""
    if get_origin(tp) is Union:
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0]
    return tp


def resolve_declared_type(model: type[BaseModel], dotted_path: str) -> Any:
    """
    Walks `dotted_path` (e.g. "sql" or "foo.bar") against `model`'s declared
    fields, returning the leaf field's annotated type (Optional unwrapped).

    Raises PathResolutionError naming the first segment that doesn't exist,
    or the first segment that isn't a nested BaseModel but the path tries to
    walk past it.
    """
    if not dotted_path:
        raise PathResolutionError("Empty dotted path.")

    current = model
    walked: list[str] = []
    parts = dotted_path.split(".")
    for i, part in enumerate(parts):
        current = unwrap_optional(current)
        if not (isinstance(current, type) and issubclass(current, BaseModel)):
            raise PathResolutionError(
                f"Field '{'.'.join(walked) or dotted_path}' does not resolve on "
                f"{model.__name__}: '{'.'.join(walked) or model.__name__}' is not "
                f"a nested model, so '{part}' cannot be reached."
            )
        field = current.model_fields.get(part)
        if field is None:
            raise PathResolutionError(
                f"Field '{part}' does not exist on {current.__name__} "
                f"(declared fields: {sorted(current.model_fields)}; full path: '{dotted_path}')."
            )
        walked.append(part)
        current = field.annotation
        if i < len(parts) - 1:
            # More path remains -- unwrap one layer of Optional so the next
            # iteration's BaseModel check sees the real nested model.
            current = unwrap_optional(current)

    return unwrap_optional(current)


def resolve_runtime_value(value: Any, dotted_path: str) -> Any:
    """
    Walks `dotted_path` against a real value (dict or BaseModel instance) at
    execution time. Returns None if any segment is missing -- plan
    validation (resolve_declared_type) is what makes an invalid path a
    rejection; this is best-effort extraction from whatever the handler
    actually stored (a plain dict for every current ExecutionHandler, see
    app/execution/contracts.py -- none of them hand back the agent's raw
    typed instance past `execute()`).
    """
    current = value
    for part in dotted_path.split("."):
        if current is None:
            return None
        if isinstance(current, BaseModel):
            current = getattr(current, part, None)
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
    return current


AdapterFn = Callable[[Any], Any]

_ADAPTERS: dict[tuple[Any, Any], AdapterFn] = {}


def register_adapter(producer_type: Any, consumer_type: Any, fn: AdapterFn) -> None:
    """Registers a hand-written conversion for a (producer_type, consumer_type)
    pair. No inferred/LLM-generated coercion is ever consulted here."""
    _ADAPTERS[(producer_type, consumer_type)] = fn


def get_adapter(producer_type: Any, consumer_type: Any) -> Optional[AdapterFn]:
    return _ADAPTERS.get((producer_type, consumer_type))


def types_compatible(producer_type: Any, consumer_type: Any) -> bool:
    """
    True when `producer_type` already satisfies `consumer_type` without an
    adapter: identical declared type, `Any` on either side, or producer_type
    is a subclass of consumer_type. This is a declared-type check (plan
    validation), not a runtime isinstance check.
    """
    if consumer_type is Any or producer_type is Any:
        return True
    if producer_type == consumer_type:
        return True
    try:
        if isinstance(producer_type, type) and isinstance(consumer_type, type):
            return issubclass(producer_type, consumer_type)
    except TypeError:
        pass
    return False


def parse_binding_ref(ref: str) -> tuple[str, str]:
    """
    Parses a Phase 25 input_bindings reference string
    ('$step.<step_id>.output.<dotted.path>') into (producer_step_id, path).
    Raises PathResolutionError if the reference doesn't match that shape --
    a plain '$step.<id>.result' string (the pre-existing untyped form) is
    deliberately not accepted here, since it names no declared output field.
    """
    if not ref.startswith("$step.") or ".output." not in ref:
        raise PathResolutionError(
            f"Malformed input_binding reference '{ref}'; expected the form "
            "'$step.<step_id>.output.<field[.nested...]>'."
        )
    remainder = ref[len("$step."):]
    dep_id, _, path = remainder.partition(".output.")
    if not dep_id or not path:
        raise PathResolutionError(
            f"Malformed input_binding reference '{ref}'; expected the form "
            "'$step.<step_id>.output.<field[.nested...]>'."
        )
    return dep_id, path


# ---------------------------------------------------------------------------
# Hand-written adapter registrations (PHASE_25.md Task 3 example).
#
# InboxFindings.extracted_commitments (list[dict]) -> ReconcilerAgent's
# ReconcileInput.items (list[ReconcileItem]): a legitimate shape conversion
# with no capability currently routing through it end-to-end (ReconcilerAgent
# is a registered Agent with no ExecutionHandler/capability wired to it yet
# -- see app/execution/registry.py), but registered here as the concrete
# example the phase names, and exercised directly in
# tests/test_agent_handoff.py.
# ---------------------------------------------------------------------------
def _extracted_commitments_to_reconcile_items(commitments: list[dict]) -> list:
    from app.agents.reconciler_agent import ReconcileItem

    return [
        ReconcileItem(
            key=str(item.get("key", "")),
            value=item.get("value"),
            source=str(item.get("source", "InboxAgent")),
        )
        for item in (commitments or [])
    ]


def _register_default_adapters() -> None:
    from app.agents.reconciler_agent import ReconcileItem

    register_adapter(list[dict], list[ReconcileItem], _extracted_commitments_to_reconcile_items)


_register_default_adapters()
