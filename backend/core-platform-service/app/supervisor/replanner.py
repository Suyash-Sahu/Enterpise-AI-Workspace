"""
Confidence-Driven Dynamic Replanning (CDRP) Module (AMOF-X Phase 4).

Evaluates low or medium confidence verification outcomes and triggers alternate-path
replanning (parameter widening or capability substitution) bounded by a configurable cap.
"""
import copy
import logging
from typing import Optional
from sqlalchemy.orm import Session

# Deterministic capability-substitution order per failed capability (Phase 10
# fix). Each entry is a preference list, not an arbitrary registry-order pick:
# it puts the most semantically-related capability first (e.g. a failed
# rag_search prefers rag_answer over an unrelated database_query) while still
# being total and cycle-safe once combined with `tried_capabilities` below --
# no two capabilities each list each other first, and nothing points back to
# itself. This alone doesn't prevent oscillation (rag_answer's own retry
# could still bounce back to rag_search's top pick); the caller-tracked
# `tried_capabilities` set is what actually guarantees no capability is
# revisited within one replanning chain.
_SUBSTITUTION_PREFERENCE: dict[str, list[str]] = {
    "rag_search": ["rag_answer", "database_query", "text_generation"],
    "rag_answer": ["text_generation", "rag_search", "database_query"],
    "database_query": ["rag_answer", "rag_search", "text_generation"],
    "text_generation": ["rag_answer", "database_query", "rag_search"],
    "document_summary": ["text_generation", "rag_answer", "rag_search"],
}

from app.core.config import settings
from app.events import Event, EventType, event_publisher
from app.models.workflow import WorkflowStep, ReplanningEvent
from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.supervisor.context import SupervisorContext
from app.supervisor.verifier import VerificationReport
from app.execution.registry import task_registry

logger = logging.getLogger(__name__)


def _build_input_template(capability: str, old_template: dict) -> dict:
    """
    Builds a fresh, capability-appropriate input_template for a capability
    substitution rather than deep-copying the failed step's template
    verbatim. Different capabilities read different primary keys --
    rag_search reads "query", rag_answer/database_query read "question",
    text_generation reads "prompt", document_summary reads "text"/"file_id"
    (see app/execution/contracts.py's handlers) -- so a verbatim copy across
    a capability swap silently drops the actual content: the new handler
    looks for a key that was never there and gets "", not an error. This
    mirrors exactly how app/supervisor/planner.py's fixed if/elif chain
    builds each capability's input_template from scratch, so a substituted
    step is indistinguishable from one the deterministic planner would have
    produced directly.
    """
    if capability == "rag_search":
        return {"query": "$context.question", "top_k": old_template.get("top_k", 5)}
    if capability == "rag_answer":
        return {"question": "$context.question", "top_k": old_template.get("top_k", 3)}
    if capability == "database_query":
        return {"question": "$context.question", "limit": old_template.get("limit", 20)}
    if capability == "text_generation":
        return {"prompt": "$context.question"}
    if capability == "document_summary":
        return {"file_id": "$context.file_id", "text": "$context.question"}
    return {"question": "$context.question"}


class ConfidenceDrivenReplanner:

    def replan(
        self,
        db: Session,
        context: SupervisorContext,
        plan: SupervisorPlan,
        failed_step: PlanStep,
        report: VerificationReport,
        replan_count: int,
        original_workflow_step_id: Optional[str] = None,
        tried_capabilities: Optional[set[str]] = None,
    ) -> tuple[Optional[PlanStep], Optional[ReplanningEvent]]:
        """
        Evaluates report.confidence_band and generates a replacement PlanStep
        or triggers human escalation if critical or if replan cap is reached.

        `tried_capabilities` should carry every capability already attempted
        earlier in this same replanning chain (the caller accumulates it
        across loop iterations); low-band substitution never picks one of
        these, falling back to critical/human escalation once none remain.
        """
        band = report.confidence_band
        logger.info(
            "[CDRP Replanner]: Evaluating step '%s' (%s) with band '%s', confidence %.2f, replan_count=%d",
            failed_step.step_id,
            failed_step.capability,
            band,
            report.confidence,
            replan_count,
        )
        event_publisher.publish(Event(
            event_type=EventType.REPLANNING_REQUESTED,
            owner_id=context.owner_id,
            trace_id=context.trace_id,
            payload={
                "step_id": failed_step.step_id,
                "capability": failed_step.capability,
                "band": band,
                "confidence": report.confidence,
                "replan_count": replan_count,
            },
        ))

        # Look up DB workflow_step if ID provided
        orig_wf_step_id = original_workflow_step_id
        if not orig_wf_step_id:
            wf_step_row = db.query(WorkflowStep).filter(
                WorkflowStep.plan_id == plan.plan_id,
                WorkflowStep.step_id == failed_step.step_id,
            ).first()
            if wf_step_row:
                orig_wf_step_id = wf_step_row.id

        # 1. Cap Enforcement
        if replan_count >= settings.CDRP_MAX_REPLANS:
            reason = f"replan cap exceeded (count={replan_count} >= max={settings.CDRP_MAX_REPLANS})"
            logger.warning("[CDRP Replanner]: %s for step '%s'", reason, failed_step.step_id)
            event = None
            if orig_wf_step_id:
                event = ReplanningEvent(
                    original_step_id=orig_wf_step_id,
                    new_step_id=None,
                    reason=reason,
                    confidence_before=report.confidence,
                )
                db.add(event)
                try:
                    db.commit()
                except Exception as exc:
                    logger.warning("[CDRP Replanner]: Failed to record cap-hit event: %s", exc)
                    db.rollback()
            return None, event

        new_step: Optional[PlanStep] = None
        reason = ""

        # 2. Medium Band: parameter widening on the same step
        if band == "medium":
            reason = f"Medium confidence ({report.confidence:.2f}): parameter widening"
            new_input = copy.deepcopy(failed_step.input_template)
            if "top_k" in new_input:
                cur_k = new_input.get("top_k", 5)
                new_input["top_k"] = int(cur_k) + 5
            elif "limit" in new_input:
                cur_lim = new_input.get("limit", 20)
                new_input["limit"] = int(cur_lim) + 20
            else:
                new_input["replan_expanded"] = True

            new_step = PlanStep(
                step_id=f"{failed_step.step_id}_replan_{replan_count + 1}",
                capability=failed_step.capability,
                purpose="capability",
                depends_on=failed_step.depends_on,
                input_template=new_input,
            )

        # 3. Low Band: capability substitution
        elif band == "low":
            reason = f"Low confidence ({report.confidence:.2f}): capability substitution"
            # Capabilities already attempted in this replanning chain (the
            # failed step itself, plus every capability the caller has
            # already tried) are excluded so a substitution can never revisit
            # one -- this is what stops rag_answer <-> text_generation (or
            # any longer cycle) from ping-ponging instead of converging.
            already_tried = set(tried_capabilities or ()) | {failed_step.capability}
            supported = task_registry.list_supported_tasks()
            alt_capability = None
            for cap in _SUBSTITUTION_PREFERENCE.get(failed_step.capability, []):
                if cap in supported and cap not in already_tried:
                    alt_capability = cap
                    break
            if not alt_capability:
                # No preference-list entry (unmapped capability) or every
                # preferred alternative was already tried: fall back to a
                # deterministic (sorted, not registration-order) scan so the
                # choice never depends on incidental handler-registration
                # order.
                for cap in sorted(supported):
                    if cap not in already_tried:
                        alt_capability = cap
                        break

            if alt_capability:
                new_step = PlanStep(
                    step_id=f"{failed_step.step_id}_replan_{replan_count + 1}",
                    capability=alt_capability,
                    purpose="capability",
                    depends_on=failed_step.depends_on,
                    input_template=_build_input_template(alt_capability, failed_step.input_template),
                )
            else:
                # Fallback to critical handling
                band = "critical"

        # 4. Critical Band (or fallback): human escalation
        if band == "critical":
            reason = f"Critical confidence band ({report.confidence:.2f}): human escalation required"
            logger.warning("[CDRP Replanner]: Step '%s' critical outcome: %s", failed_step.step_id, reason)
            event = None
            if orig_wf_step_id:
                event = ReplanningEvent(
                    original_step_id=orig_wf_step_id,
                    new_step_id=None,
                    reason=reason,
                    confidence_before=report.confidence,
                )
                db.add(event)
                try:
                    db.commit()
                except Exception as exc:
                    logger.warning("[CDRP Replanner]: Failed to record critical event: %s", exc)
                    db.rollback()
            return None, event

        # Log & record ReplanningEvent if new_step created
        event = None
        if new_step and orig_wf_step_id:
            event = ReplanningEvent(
                original_step_id=orig_wf_step_id,
                new_step_id=None,  # Updated when new step is persisted
                reason=reason,
                confidence_before=report.confidence,
            )
            db.add(event)
            try:
                db.commit()
            except Exception as exc:
                logger.warning("[CDRP Replanner]: Failed to commit ReplanningEvent: %s", exc)
                db.rollback()

        return new_step, event


cdrp_replanner = ConfidenceDrivenReplanner()
