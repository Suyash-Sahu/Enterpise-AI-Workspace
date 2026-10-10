import hashlib
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.database import SessionLocal
from app.execution.registry import task_registry
from app.models.decomposition_attempt import DecompositionAttempt
from app.runtime.exceptions import RuntimePolicyError
from app.schemas.runtime import RuntimeGenerateRequest
from app.schemas.supervisor import IntentResult, PlanStep
from app.services.runtime_service import runtime_service
from app.supervisor.context import SupervisorContext
from app.supervisor.policies import supervisor_policy
from app.utils.json_extract import extract_json

logger = logging.getLogger(__name__)

DECOMPOSER_VERSION = "atgo-llm-v2"

_KEYWORD_GROUPS: dict[str, tuple[str, ...]] = {
    "database_query": ("database", "sql", "table of records"),
    "rag_search": ("search", "look up", "drive"),
    "document_summary": ("summar",),
    "gmail.send": ("send an email", "send email", "email to"),
}

_DOMAIN_INDICATORS: dict[str, tuple[str, ...]] = {
    "database": ("database", "sql", "table", "records", "rows", "select", "how many", "count", "query"),
    "rag": ("document", "index", "file", "drive", "search", "pdf", "content", "knowledge", "indexed"),
    "gmail": ("email", "gmail", "send", "message", "inbox", "mail", "draft"),
    "summary": ("summary", "summarize", "digest"),
    "workgraph": ("task", "workgraph", "action item", "project"),
}


def _hash_objective(question: str) -> str:
    return hashlib.sha256(question.strip().encode("utf-8")).hexdigest()


def _looks_multi_source_keyword(question: str) -> bool:
    q = question.lower()
    hit_groups = {
        group for group, keywords in _KEYWORD_GROUPS.items()
        if any(kw in q for kw in keywords)
    }
    return len(hit_groups) >= 2


def _looks_multi_source_coverage(question: str, intent: IntentResult) -> bool:
    q = question.lower()
    detected_domains = {
        domain for domain, kw_list in _DOMAIN_INDICATORS.items()
        if any(kw in q for kw in kw_list)
    }

    # Include intent capability domain if recognized
    cap = intent.capability
    if cap.startswith("rag"):
        detected_domains.add("rag")
    elif cap.startswith("database"):
        detected_domains.add("database")
    elif cap.startswith("gmail") or cap.startswith("inbox"):
        detected_domains.add("gmail")
    elif cap.startswith("document_summary"):
        detected_domains.add("summary")

    return len(detected_domains) >= 2


def _should_decompose(context: SupervisorContext, intent: IntentResult) -> bool:
    mode = settings.DECOMPOSER_MODE.lower()
    if mode == "off":
        return False
    if mode == "keyword":
        return _looks_multi_source_keyword(context.question)
    # Default: "coverage"
    return _looks_multi_source_coverage(context.question, intent)


def _record_attempt(
    db: Optional[Session],
    context: SupervisorContext,
    mode: str,
    attempt_number: int,
    raw_output: Optional[str],
    accepted: bool,
    rejection_reason: Optional[str],
) -> None:
    local_db = False
    if db is None:
        db = SessionLocal()
        local_db = True
    try:
        rec = DecompositionAttempt(
            request_id=context.request_id,
            owner_id=context.owner_id,
            objective_hash=_hash_objective(context.question),
            decomposer_mode=mode,
            attempt_number=attempt_number,
            raw_output=raw_output,
            accepted=accepted,
            rejection_reason=rejection_reason,
        )
        db.add(rec)
        db.commit()
    except Exception as exc:
        logger.warning("[ATGO decomposer]: failed to persist DecompositionAttempt: %s", exc)
        if local_db:
            db.rollback()
    finally:
        if local_db and db:
            db.close()


def _parse_and_validate(raw_text: str) -> tuple[Optional[list[PlanStep]], Optional[str]]:
    parsed = extract_json(raw_text)
    if not parsed:
        return (None, "unparseable LLM output: not valid JSON")

    steps_raw = parsed.get("steps")
    if not isinstance(steps_raw, list):
        return (None, "malformed step shape: 'steps' key is not a list")

    if len(steps_raw) < 2:
        return (None, f"under-length plan: produced {len(steps_raw)} step(s), minimum 2 required for decomposition")

    if len(steps_raw) > settings.SUPERVISOR_MAX_STEPS:
        return (None, f"plan exceeds maximum allowed steps ({len(steps_raw)} > {settings.SUPERVISOR_MAX_STEPS})")

    try:
        steps = [
            PlanStep(
                step_id=str(raw.get("step_id") or f"step_{i+1}"),
                capability=str(raw.get("capability", "")),
                purpose="synthesis" if raw.get("capability") == "text_generation" and raw.get("depends_on") else "capability",
                depends_on=[str(d) for d in raw.get("depends_on", [])],
                input_template=dict(raw.get("input_template", {})),
                input_bindings=dict(raw.get("input_bindings", {})),
            )
            for i, raw in enumerate(steps_raw)
        ]
    except Exception as exc:
        return (None, f"malformed step shape: {exc}")

    try:
        supervisor_policy.validate_dag_plan(steps)
    except RuntimePolicyError as exc:
        return (None, str(exc))

    return (steps, None)


class TaskDecomposer:
    """
    AMOF-X Phase 28 (ATGO v2): Multi-Step Task Decomposition with domain coverage,
    1-retry LLM repair pass, and telemetry audit trail.
    """

    def maybe_decompose(
        self,
        context: SupervisorContext,
        intent: IntentResult,
        db: Optional[Session] = None,
    ) -> Optional[list[PlanStep]]:
        mode = settings.DECOMPOSER_MODE.lower()
        if not _should_decompose(context, intent):
            return None

        capabilities = task_registry.list_capabilities()
        capability_list = "\n".join(
            f"- {c['task_type']}: {c['description']}" for c in capabilities
        )

        system_prompt = (
            "You are a task decomposition planner. Given a user objective, break it "
            "into a directed acyclic graph of steps. You may ONLY use these exact "
            "capability names -- inventing any other capability is not allowed:\n"
            f"{capability_list}\n\n"
            "Respond with ONLY a JSON object of this exact shape, no prose:\n"
            '{"steps": [{"step_id": "step_1", "capability": "<name from list>", '
            '"depends_on": [], "input_template": {"question": "$context.question"}}]}\n'
            "Rules:\n"
            "- Independent steps must have depends_on: [].\n"
            "- Synthesis step capability is 'text_generation', listing source step_ids in depends_on.\n"
            '- Optional typed input handoff: "input_bindings": {"<field>": "$step.<id>.output.<field>"}.\n'
            f"- Emit at most {settings.SUPERVISOR_MAX_STEPS} steps total, minimum 2 steps."
        )

        # Attempt 1
        try:
            resp_1 = runtime_service.generate(
                RuntimeGenerateRequest(
                    prompt=context.question,
                    system_prompt=system_prompt,
                    execution_mode=context.execution_mode,
                    timeout=context.timeout,
                    request_id=context.request_id,
                    metadata={"classification_content": context.question},
                )
            )
            raw_1 = resp_1.completion
        except Exception as exc:
            logger.warning("[ATGO decomposer]: generation call failed: %s", exc)
            _record_attempt(db, context, mode, 1, None, False, f"generation call failed: {exc}")
            return None

        steps_1, reason_1 = _parse_and_validate(raw_1)
        if steps_1:
            _record_attempt(db, context, mode, 1, raw_1, True, None)
            return steps_1

        _record_attempt(db, context, mode, 1, raw_1, False, reason_1)
        logger.info("[ATGO decomposer]: Attempt 1 rejected (%s). Attempting repair pass...", reason_1)

        # Attempt 2: 1-retry Repair Pass
        repair_prompt = (
            f"YOUR PREVIOUS ATTEMPT WAS REJECTED WITH VALIDATION ERROR:\n{reason_1}\n\n"
            f"PREVIOUS RAW OUTPUT WAS:\n{raw_1}\n\n"
            "Please fix the validation error above and emit a valid JSON plan for the objective."
        )

        try:
            resp_2 = runtime_service.generate(
                RuntimeGenerateRequest(
                    prompt=f"{context.question}\n\n{repair_prompt}",
                    system_prompt=system_prompt,
                    execution_mode=context.execution_mode,
                    timeout=context.timeout,
                    request_id=context.request_id,
                    metadata={"classification_content": context.question},
                )
            )
            raw_2 = resp_2.completion
        except Exception as exc:
            logger.warning("[ATGO decomposer]: repair generation call failed: %s", exc)
            _record_attempt(db, context, mode, 2, None, False, f"repair generation call failed: {exc}")
            return None

        steps_2, reason_2 = _parse_and_validate(raw_2)
        if steps_2:
            _record_attempt(db, context, mode, 2, raw_2, True, None)
            logger.info("[ATGO decomposer]: Repair pass succeeded.")
            return steps_2

        _record_attempt(db, context, mode, 2, raw_2, False, reason_2)
        logger.warning("[ATGO decomposer]: Repair pass rejected (%s). Falling back to fixed planner.", reason_2)
        return None


task_decomposer = TaskDecomposer()
