import uuid
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.schemas.supervisor import IntentResult, PlanStep, SupervisorPlan
from app.supervisor.context import SupervisorContext
from app.supervisor.decomposer import DECOMPOSER_VERSION, task_decomposer
from app.supervisor.policies import supervisor_policy
from app.agents.registry import agent_registry
from app.agents.handoff import (
    CAPABILITY_AGENT_MAP,
    PathResolutionError,
    get_adapter,
    parse_binding_ref,
    resolve_declared_type,
    resolve_runtime_value,
    types_compatible,
    unwrap_optional,
)

logger = logging.getLogger(__name__)


class SupervisorPlanner:

    def build_plan(self, context: SupervisorContext, intent: IntentResult, db: Optional[Session] = None) -> SupervisorPlan:
        """
        Generates single-step or multi-step DAG plan based on resolved IntentResult.
        """
        plan_id = f"plan_{uuid.uuid4().hex[:10]}"
        steps: list[PlanStep] = []
        decomposer_version: str | None = None

        q = context.question

        # ATGO: for objectives that look like they span more than one
        # source, try the LLM-driven decomposer first. It only ever returns
        # a plan that has already passed the same validate_dag_plan() gate
        # the fixed planner below is validated against, and returns None on
        # anything ambiguous -- so a genuinely single-source query still
        # falls through to the deterministic mapping unchanged.
        decomposed_steps = task_decomposer.maybe_decompose(context=context, intent=intent, db=db)
        if decomposed_steps:
            steps = decomposed_steps
            decomposer_version = DECOMPOSER_VERSION

        # Single-step Intent Mappings
        elif "send email" in q.lower() or "send an email" in q.lower() or intent.capability == "gmail.send":
            steps.append(
                PlanStep(
                    step_id="step_1",
                    capability="gmail.send",
                    purpose="capability",
                    depends_on=[],
                    input_template={"to": "recipient@example.com", "subject": "Email Notice", "body": "$context.question"},
                )
            )
        elif intent.capability == "database_query":
            steps.append(
                PlanStep(
                    step_id="step_1",
                    capability="database_query",
                    purpose="capability",
                    depends_on=[],
                    input_template={"question": "$context.question", "limit": 20},
                )
            )
        elif intent.capability == "rag_search":
            steps.append(
                PlanStep(
                    step_id="step_1",
                    capability="rag_search",
                    purpose="capability",
                    depends_on=[],
                    input_template={"query": "$context.question", "top_k": 5},
                )
            )
        elif intent.capability == "rag_answer":
            steps.append(
                PlanStep(
                    step_id="step_1",
                    capability="rag_answer",
                    purpose="capability",
                    depends_on=[],
                    input_template={"question": "$context.question", "top_k": 3},
                )
            )
        elif intent.capability == "document_summary":
            steps.append(
                PlanStep(
                    step_id="step_1",
                    capability="document_summary",
                    purpose="capability",
                    depends_on=[],
                    input_template={
                        "file_id": "$context.file_id",
                        "text": "$context.question",
                    },
                )
            )
        else:
            # Default text_generation
            steps.append(
                PlanStep(
                    step_id="step_1",
                    capability="text_generation",
                    purpose="capability",
                    depends_on=[],
                    input_template={"prompt": "$context.question"},
                )
            )

        # Validate DAG plan boundaries
        supervisor_policy.validate_dag_plan(steps)

        return SupervisorPlan(
            plan_id=plan_id,
            request_id=context.request_id,
            steps=steps,
            decomposer_version=decomposer_version,
            max_steps=settings.SUPERVISOR_MAX_STEPS,
        )

    @staticmethod
    def resolve_step_input(
        step: PlanStep,
        context: SupervisorContext,
        completed_steps: dict[str, PlanStep],
    ) -> dict[str, Any]:
        """
        Resolves allowlisted input templates ($context.question, $step.step_1.result,
        $state.<key>). Prohibits arbitrary string/code evaluation -- exactly four
        fixed prefixes, no attribute-path traversal, no eval/exec.

        Phase 25: after resolving `input_template` (unchanged, above), also
        resolves `step.input_bindings` -- typed, field-level handoffs already
        checked at plan-validation time (see
        app/supervisor/policies.py::validate_dag_plan) -- and merges them in,
        overriding any `input_template` key of the same name.
        """
        resolved = {}
        for key, val in step.input_template.items():
            if isinstance(val, str):
                if val == "$context.question":
                    resolved[key] = context.question
                elif val == "$context.file_id":
                    resolved[key] = context.file_id
                elif val.startswith("$state."):
                    # e.g. "$state.step.step_1" or "$state.inbox_findings"
                    state_key = val[len("$state."):]
                    if context.blackboard is not None and state_key:
                        resolved[key] = context.blackboard.get(state_key)
                    else:
                        # Fail closed to None -- same tolerance as the
                        # $step. branch below for a missing dependency,
                        # not a raised error, so a legacy caller that never
                        # attached a blackboard doesn't crash the run.
                        resolved[key] = None
                elif val.startswith("$step."):
                    # e.g. "$step.step_1.result" -- the untyped form
                    # PHASE_25.md Task 5 keeps working unchanged for
                    # capabilities not yet migrated to input_bindings, but is
                    # deprecated: logged so remaining call sites are visible.
                    logger.warning(
                        "[Planner] step '%s' key '%s' uses the deprecated untyped "
                        "'$step.X.result' form ('%s'); migrate to input_bindings "
                        "(see app/schemas/supervisor.py::PlanStep.input_bindings).",
                        step.step_id, key, val,
                    )
                    parts = val.split(".")
                    if len(parts) >= 2:
                        dep_id = parts[1]
                        dep_step = completed_steps.get(dep_id)
                        if dep_step and dep_step.result:
                            resolved[key] = dep_step.result.get("result", dep_step.result)
                        else:
                            resolved[key] = None
                    else:
                        resolved[key] = val
                else:
                    resolved[key] = val
            else:
                resolved[key] = val

        for field_name, ref in step.input_bindings.items():
            resolved[field_name] = SupervisorPlanner._resolve_typed_binding(
                step=step, field_name=field_name, ref=ref, completed_steps=completed_steps,
            )

        return resolved

    @staticmethod
    def _resolve_typed_binding(
        step: PlanStep,
        field_name: str,
        ref: str,
        completed_steps: dict[str, PlanStep],
    ) -> Any:
        """
        Runtime counterpart to policies.py's plan-time input_bindings check:
        extracts the real value at `ref`'s dotted path from the completed
        producer step's stored result, applying the same adapter (if any)
        that plan validation confirmed was available for this exact
        (producer field, consumer field) pair.

        Fails closed to None on a missing/incomplete producer step -- the
        same tolerance resolve_step_input's `$step.` branch already has for
        a dependency that hasn't completed -- since a genuinely invalid
        binding was already rejected at plan-validation time and can't reach
        here.
        """
        try:
            dep_id, path = parse_binding_ref(ref)
        except PathResolutionError:
            logger.warning(
                "[Planner] step '%s' has a malformed input_binding ref '%s' "
                "that plan validation should have rejected.", step.step_id, ref,
            )
            return None

        dep_step = completed_steps.get(dep_id)
        if not dep_step or dep_step.result is None:
            return None

        raw = dep_step.result.get("result", dep_step.result) if isinstance(dep_step.result, dict) else dep_step.result
        value = resolve_runtime_value(raw, path)

        producer_agent_name = CAPABILITY_AGENT_MAP.get(dep_step.capability)
        consumer_agent_name = CAPABILITY_AGENT_MAP.get(step.capability)
        if not producer_agent_name or not consumer_agent_name:
            return value

        try:
            producer_type = resolve_declared_type(
                agent_registry.get_agent(producer_agent_name).spec.output_schema, path,
            )
        except PathResolutionError:
            return value

        consumer_field = agent_registry.get_agent(consumer_agent_name).spec.input_schema.model_fields.get(field_name)
        if consumer_field is None:
            return value

        consumer_type = unwrap_optional(consumer_field.annotation)
        if types_compatible(producer_type, consumer_type):
            return value

        adapter = get_adapter(producer_type, consumer_type)
        return adapter(value) if adapter else value


supervisor_planner = SupervisorPlanner()
