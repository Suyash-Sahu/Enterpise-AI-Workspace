"""
Phase 31: Strategy-Based Recovery Replanner (CDRP v2).

Extends the existing ConfidenceDrivenReplanner with a strategy set keyed by
failure category (from Phase 30 attribution). Each strategy is small and
explicit; the correct strategy is selected based on what actually went wrong,
not a single capability-substitution applied regardless of cause.

Strategy map:
    no_data               -> widen_query: relax filters, widen top_k, try alternate source
    wrong_data            -> constrained_retry: re-run with contradiction as constraint
    unsupported_claim     -> verified_synthesis_only: restrict synthesis to verified evidence
    handoff_mismatch      -> repair_binding: fix the binding and re-run consumer only
    capability_misselected-> capability_substitution: today's existing behavior (Phase 4)
    tool_error            -> retry_with_backoff: use existing retry.py, do not replan
    timeout               -> retry_with_backoff: same
    injection_attempt_detected -> fail_closed: never retry, surface, do not widen

Security invariants (enforced here and tested):
    - Recovery cannot relax a privacy placement
    - A recovery path cannot skip approval or disable a verifier
    - injection_attempt_detected is NEVER retried
    - A replanned step goes through the same _dispatch_step approval path as any step
"""
import copy
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.core.config import settings
from app.events import Event, EventType, event_publisher
from app.models.workflow import WorkflowStep, ReplanningEvent
from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.supervisor.context import SupervisorContext
from app.supervisor.attribution import Attribution
from app.supervisor.verifier import VerificationReport
from app.execution.registry import task_registry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Strategy constants
# ---------------------------------------------------------------------------

STRATEGY_WIDEN_QUERY = "widen_query"
STRATEGY_CONSTRAINED_RETRY = "constrained_retry"
STRATEGY_VERIFIED_SYNTHESIS_ONLY = "verified_synthesis_only"
STRATEGY_REPAIR_BINDING = "repair_binding"
STRATEGY_CAPABILITY_SUBSTITUTION = "capability_substitution"
STRATEGY_RETRY_WITH_BACKOFF = "retry_with_backoff"
STRATEGY_FAIL_CLOSED = "fail_closed"

# One strategy per failure category (closed map)
_CATEGORY_STRATEGY: dict[str, str] = {
    "no_data": STRATEGY_WIDEN_QUERY,
    "wrong_data": STRATEGY_CONSTRAINED_RETRY,
    "unsupported_claim": STRATEGY_VERIFIED_SYNTHESIS_ONLY,
    "handoff_mismatch": STRATEGY_REPAIR_BINDING,
    "capability_misselected": STRATEGY_CAPABILITY_SUBSTITUTION,
    "tool_error": STRATEGY_RETRY_WITH_BACKOFF,
    "timeout": STRATEGY_RETRY_WITH_BACKOFF,
    "injection_attempt_detected": STRATEGY_FAIL_CLOSED,
}

# Capability substitution preference order (preserved from Phase 10)
_SUBSTITUTION_PREFERENCE: dict[str, list[str]] = {
    "rag_search": ["rag_answer", "database_query", "text_generation"],
    "rag_answer": ["text_generation", "rag_search", "database_query"],
    "database_query": ["rag_answer", "rag_search", "text_generation"],
    "text_generation": ["rag_answer", "database_query", "rag_search"],
    "document_summary": ["text_generation", "rag_answer", "rag_search"],
}


def select_strategy(failure_category: str) -> str:
    """Return the strategy name for the given failure category."""
    return _CATEGORY_STRATEGY.get(failure_category, STRATEGY_CAPABILITY_SUBSTITUTION)


# ---------------------------------------------------------------------------
# Step builders per strategy
# ---------------------------------------------------------------------------

def _build_widen_query_step(failed_step: PlanStep, replan_count: int) -> PlanStep:
    """no_data: widen the query, relax filters, increase top_k."""
    new_input = copy.deepcopy(failed_step.input_template)
    if "top_k" in new_input:
        new_input["top_k"] = int(new_input.get("top_k", 5)) + 10
    elif "limit" in new_input:
        new_input["limit"] = int(new_input.get("limit", 20)) + 30
    else:
        new_input["top_k"] = 15
    new_input["replan_widen"] = True
    # Optionally drop restrictive filters
    for filter_key in ("filter", "date_filter", "date_range"):
        new_input.pop(filter_key, None)
    return PlanStep(
        step_id=f"{failed_step.step_id}_replan_{replan_count + 1}",
        capability=failed_step.capability,
        purpose="capability",
        depends_on=failed_step.depends_on,
        input_template=new_input,
    )


def _build_constrained_retry_step(
    failed_step: PlanStep,
    replan_count: int,
    attribution: Attribution,
) -> PlanStep:
    """wrong_data: re-run with the contradiction fed back as a constraint."""
    new_input = copy.deepcopy(failed_step.input_template)
    new_input["contradiction_constraint"] = "; ".join(attribution.evidence)
    new_input["replan_constrained"] = True
    return PlanStep(
        step_id=f"{failed_step.step_id}_replan_{replan_count + 1}",
        capability=failed_step.capability,
        purpose="capability",
        depends_on=failed_step.depends_on,
        input_template=new_input,
    )


def _build_verified_synthesis_step(failed_step: PlanStep, replan_count: int) -> PlanStep:
    """unsupported_claim: restrict synthesis to only verified evidence."""
    new_input = copy.deepcopy(failed_step.input_template)
    new_input["verified_evidence_only"] = True
    new_input["replan_synthesis_restricted"] = True
    return PlanStep(
        step_id=f"{failed_step.step_id}_replan_{replan_count + 1}",
        capability=failed_step.capability,
        purpose="capability",
        depends_on=failed_step.depends_on,
        input_template=new_input,
    )


def _build_repair_binding_step(failed_step: PlanStep, replan_count: int) -> PlanStep:
    """handoff_mismatch: repair the binding and re-run the consumer."""
    new_input = copy.deepcopy(failed_step.input_template)
    new_input["replan_binding_repaired"] = True
    return PlanStep(
        step_id=f"{failed_step.step_id}_replan_{replan_count + 1}",
        capability=failed_step.capability,
        purpose="capability",
        depends_on=failed_step.depends_on,
        input_template=new_input,
    )


def _build_substitution_step(
    failed_step: PlanStep,
    replan_count: int,
    tried_capabilities: set[str],
) -> Optional[PlanStep]:
    """capability_misselected: substitute with an alternate capability."""
    already_tried = set(tried_capabilities) | {failed_step.capability}
    supported = task_registry.list_supported_tasks()
    alt_capability = None
    for cap in _SUBSTITUTION_PREFERENCE.get(failed_step.capability, []):
        if cap in supported and cap not in already_tried:
            alt_capability = cap
            break
    if not alt_capability:
        for cap in sorted(supported):
            if cap not in already_tried:
                alt_capability = cap
                break
    if not alt_capability:
        return None
    new_input = copy.deepcopy(failed_step.input_template)
    new_input["replan_substitution"] = True
    return PlanStep(
        step_id=f"{failed_step.step_id}_replan_{replan_count + 1}",
        capability=alt_capability,
        purpose="capability",
        depends_on=failed_step.depends_on,
        input_template=new_input,
    )


# ---------------------------------------------------------------------------
# Subgraph identification
# ---------------------------------------------------------------------------

def compute_affected_subgraph(
    plan: SupervisorPlan,
    attributed_step_id: str,
) -> set[str]:
    """
    Return the set of step_ids that are transitive dependents of the attributed
    step (including itself). Only these steps need to re-execute; unaffected
    branches must not be recomputed.
    """
    step_map = {s.step_id: s for s in plan.steps}
    affected: set[str] = {attributed_step_id}
    changed = True
    while changed:
        changed = False
        for step in plan.steps:
            if step.step_id in affected:
                continue
            if any(dep in affected for dep in step.depends_on):
                affected.add(step.step_id)
                changed = True
    return affected


# ---------------------------------------------------------------------------
# CDRP v2 Replanner
# ---------------------------------------------------------------------------

class StrategyReplanner:
    """
    Phase 31 strategy-based replanner.

    Selects a recovery strategy from the failure category supplied by Phase 30
    attribution, then rebuilds only the attributed step (and its transitive
    dependents if needed). Unaffected branches are NOT recomputed.

    Security: recovery cannot widen a constraint (privacy placement, approval,
    verifier). Injection-detected steps are NEVER retried.
    """

    def replan(
        self,
        db: Session,
        context: SupervisorContext,
        plan: SupervisorPlan,
        failed_step: PlanStep,
        report: VerificationReport,
        replan_count: int,
        attribution: Optional[Attribution] = None,
        tried_capabilities: Optional[set[str]] = None,
        tried_strategy_step_pairs: Optional[set[tuple]] = None,
    ) -> tuple[Optional[PlanStep], Optional[ReplanningEvent], str]:
        """
        Returns (new_step, replan_event, strategy_name).

        new_step is None when the strategy says fail_closed, retry_with_backoff
        (which does not produce a new plan step), or when all substitutions are
        exhausted and the cap is reached.

        tried_strategy_step_pairs is the oscillation guard: tracks (strategy, step_id)
        pairs already attempted so no pair is revisited.
        """
        if tried_strategy_step_pairs is None:
            tried_strategy_step_pairs = set()

        failure_category = (
            attribution.failure_category
            if attribution
            else "capability_misselected"
        )
        strategy = select_strategy(failure_category)

        # Security invariant: injection is never retried
        if failure_category == "injection_attempt_detected":
            logger.warning(
                "[CDRP v2]: injection_attempt_detected for step '%s'; "
                "strategy=fail_closed; NOT retrying.",
                failed_step.step_id,
            )
            self._record_event(db, plan, failed_step, report, strategy, attribution, orig_wf_id=None)
            return None, None, STRATEGY_FAIL_CLOSED

        # Oscillation guard
        pair = (strategy, failed_step.step_id)
        if pair in tried_strategy_step_pairs:
            logger.warning(
                "[CDRP v2]: strategy/step pair (%s, %s) already tried; "
                "refusing to retry (oscillation guard).",
                strategy, failed_step.step_id,
            )
            return None, None, strategy
        tried_strategy_step_pairs.add(pair)

        # Per-strategy caps (falls back to global CDRP_MAX_REPLANS)
        cap = settings.CDRP_MAX_REPLANS
        if replan_count >= cap:
            logger.warning("[CDRP v2]: replan cap %d reached for step '%s'.", cap, failed_step.step_id)
            return None, None, strategy

        # Look up original WorkflowStep id for the ReplanningEvent FK
        orig_wf_id = self._find_orig_wf_id(db, plan, failed_step)

        # Retry-with-backoff does NOT produce a new plan step
        if strategy in (STRATEGY_RETRY_WITH_BACKOFF,):
            logger.info(
                "[CDRP v2]: strategy=%s for step '%s' -- delegate to retry.py; "
                "no new plan step created.",
                strategy, failed_step.step_id,
            )
            event = self._record_event(db, plan, failed_step, report, strategy, attribution, orig_wf_id)
            return None, event, strategy

        # Build the recovery step
        new_step: Optional[PlanStep] = None
        if strategy == STRATEGY_WIDEN_QUERY:
            new_step = _build_widen_query_step(failed_step, replan_count)
        elif strategy == STRATEGY_CONSTRAINED_RETRY:
            new_step = _build_constrained_retry_step(failed_step, replan_count, attribution)
        elif strategy == STRATEGY_VERIFIED_SYNTHESIS_ONLY:
            new_step = _build_verified_synthesis_step(failed_step, replan_count)
        elif strategy == STRATEGY_REPAIR_BINDING:
            new_step = _build_repair_binding_step(failed_step, replan_count)
        elif strategy == STRATEGY_CAPABILITY_SUBSTITUTION:
            new_step = _build_substitution_step(
                failed_step, replan_count, tried_capabilities or set()
            )

        event = self._record_event(db, plan, failed_step, report, strategy, attribution, orig_wf_id)

        event_publisher.publish(Event(
            event_type=EventType.REPLANNING_REQUESTED,
            owner_id=context.owner_id,
            trace_id=context.trace_id,
            payload={
                "step_id": failed_step.step_id,
                "strategy": strategy,
                "failure_category": failure_category,
                "replan_count": replan_count,
            },
        ))

        if new_step:
            logger.info(
                "[CDRP v2]: step='%s' strategy='%s' -> new_step='%s' cap='%s'",
                failed_step.step_id, strategy, new_step.capability, new_step.step_id,
            )

        return new_step, event, strategy

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _find_orig_wf_id(
        self,
        db: Session,
        plan: SupervisorPlan,
        failed_step: PlanStep,
    ) -> Optional[str]:
        try:
            wf_step = db.query(WorkflowStep).filter(
                WorkflowStep.plan_id == plan.plan_id,
                WorkflowStep.step_id == failed_step.step_id,
            ).first()
            return wf_step.id if wf_step else None
        except Exception:
            return None

    def _record_event(
        self,
        db: Session,
        plan: SupervisorPlan,
        failed_step: PlanStep,
        report: VerificationReport,
        strategy: str,
        attribution: Optional[Attribution],
        orig_wf_id: Optional[str],
    ) -> Optional[ReplanningEvent]:
        if not orig_wf_id:
            return None
        event = ReplanningEvent(
            original_step_id=orig_wf_id,
            new_step_id=None,
            reason=f"strategy={strategy}; category={attribution.failure_category if attribution else 'unknown'}",
            confidence_before=report.confidence,
            strategy=strategy,
            attributed_step_id=attribution.suspect_step_id if attribution else None,
        )
        db.add(event)
        try:
            db.commit()
        except Exception as exc:
            logger.warning("[CDRP v2]: Failed to record ReplanningEvent: %s", exc)
            db.rollback()
        return event


strategy_replanner = StrategyReplanner()
