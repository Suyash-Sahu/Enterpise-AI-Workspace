import time
import json
import logging
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor
from sqlalchemy.orm import Session
from app.db.database import SessionLocal

from app.models.workflow import WorkflowPlan, WorkflowStep, FailureAttribution
from app.models.routing_decision import RoutingDecisionRecord
from app.schemas.supervisor import (
    SupervisorResponse,
    SupervisorPlan,
    IntentResult,
    PlanStep,
)
from app.agents.base import AgentResult
from app.agents.registry import agent_registry
from app.agents.handoff import CAPABILITY_AGENT_MAP
from app.supervisor.blackboard import RunBlackboard
from app.supervisor.context import SupervisorContext
from app.supervisor.intent import intent_analyzer
from app.supervisor.policies import supervisor_policy
from app.supervisor.planner import supervisor_planner
from app.supervisor.scheduler import DagScheduler
from app.supervisor.execution_router import supervisor_execution_router
from app.supervisor.aggregator import result_aggregator
from app.supervisor.synthesizer import response_synthesizer
from app.supervisor.verifier import response_verifier, VerificationReport
from app.supervisor.verifiers import verify_step, verification_mode_for_run
from app.supervisor.replanner import cdrp_replanner
from app.supervisor.attribution import failure_attributor, Attribution
from app.events import Event, EventType, event_publisher
from app.core.config import settings
from app.schemas.approval import ApprovalCreate
from app.services.approval.approval_policy import approval_policy
from app.services.approval.approval_service import approval_service

logger = logging.getLogger(__name__)

# Phase 24: capability -> registered-agent-name correspondence, used only to
# decide whether a completed step's result should also be written under that
# agent's declared `writes_state` keys (in addition to the unconditional
# `step.<step_id>` write every completed step gets, below).
#
# Verified against app/execution/contracts.py, not guessed: each entry here
# is a capability whose ExecutionHandler.execute() genuinely constructs and
# calls that exact registered Agent (e.g. InboxClassifyHandler literally
# calls `inbox_triage_agent.run(...)`, whose spec.name is "InboxAgent").
# text_generation, gmail.send, workgraph.create_task, digest.daily and
# database_report are deliberately absent -- their handlers call
# runtime_service / the underlying services directly, not a registered
# Agent, so mapping them here would misattribute state to an agent that
# never ran. Of the agents mapped below, only InboxAgent currently declares
# a non-empty `writes_state` (["inbox_findings"]); the others resolve here
# but write nothing extra, which is the "wire it so it fires when populated"
# behavior the phase asks for.
#
# Phase 25: this mapping now lives in app/agents/handoff.py (imported above)
# so app/supervisor/policies.py and app/supervisor/planner.py can reuse the
# exact same producer/consumer capability->agent lookup for typed
# input_bindings validation/resolution without a circular import through
# this module (which itself imports planner.py). Re-exported here under the
# same name so nothing else that imports it from this module breaks.


def _write_step_to_blackboard(context: SupervisorContext, step_id: str, capability: str, result: Any, db_sess: Session | None = None) -> None:
    """
    Writes a completed step's result to the run blackboard under two keys:
    always `step.<step_id>`, and additionally each key the mapped agent (if
    any, per CAPABILITY_AGENT_MAP) declares in its AgentSpec.writes_state.
    """
    if context.blackboard is None or result is None:
        return

    wrapped = AgentResult(output=result)
    context.blackboard.put(f"step.{step_id}", wrapped, written_by=step_id, db_sess=db_sess)

    agent_name = CAPABILITY_AGENT_MAP.get(capability)
    if not agent_name:
        return
    try:
        spec = agent_registry.get_agent(agent_name).spec
    except ValueError:
        logger.warning("[P7 Supervisor]: CAPABILITY_AGENT_MAP points at unregistered agent '%s'.", agent_name)
        return
    for state_key in spec.writes_state:
        context.blackboard.put(state_key, wrapped, written_by=step_id, db_sess=db_sess)


def _verify_completed_step(
    db: Session,
    context: SupervisorContext,
    plan_id: str,
    step: PlanStep,
    resolved_input: dict,
) -> bool:
    """
    Phase 29: per-step verification gate, run after a step completes and
    before its result is written to the blackboard. A failed verification
    stops the result from reaching shared state, so a bad producer output
    cannot silently poison downstream agents that consume $state.* or
    typed bindings.

    Side effects, in order:
    1. Persist the report to WorkflowStep.verification_json (best effort --
       a report that cannot be persisted must not fail the run; the
       step-failure path below is the load-bearing behavior).
    2. Publish step_verification_completed alongside the existing
       agent_started/agent_completed lifecycle events.

    Returns True when the step is usable (PASSED / UNVERIFIED); False when
    the step FAILED verification.

    The WorkflowStep row is looked up on the session this function is given
    (`db`) -- in parallel execution this is the worker thread's own session,
    never the request-scoped one that owns wf_step_rows, so no WorkflowStep
    ORM object crosses a session/thread boundary here.

    Mode resolution lives in verification_mode_for_run(): "off"/"final_only"
    return UNVERIFIED without persisting, exactly reproducing pre-Phase-29
    behavior for those arms (verification_json stays NULL, no event).
    """
    mode = verification_mode_for_run(context)
    if mode in ("off", "final_only"):
        return True

    wf_step = db.query(WorkflowStep).filter(
        WorkflowStep.plan_id == plan_id,
        WorkflowStep.step_id == step.step_id,
    ).first()

    try:
        report = verify_step(
            capability=step.capability,
            inputs=resolved_input,
            output=step.result,
            evidence=[],
            owner_id=context.owner_id,
        )
    except Exception as e:
        # Verification infrastructure failure must not crash a run that just
        # completed successfully -- record UNVERIFIED and let it through,
        # same degraded-mode discipline as the event publisher.
        logger.warning("[P7 Supervisor]: per-step verification raised for %s: %s", step.step_id, e)
        report = VerificationReport(
            status="UNVERIFIED", confidence=0.5,
            checks={"error": str(e)}, failures=[],
        )

    if wf_step is not None:
        try:
            wf_step.verification_json = json.dumps(report.to_dict())
            db.commit()
        except Exception as e:
            logger.warning("[P7 Supervisor]: Failed to commit verification report for step %s: %s", step.step_id, e)
            db.rollback()

    event_publisher.publish(Event(
        event_type=EventType.STEP_VERIFICATION_COMPLETED,
        owner_id=context.owner_id,
        trace_id=context.trace_id,
        payload={
            "step_id": step.step_id,
            "capability": step.capability,
            "status": report.status,
            "confidence": report.confidence,
            "band": report.confidence_band,
            "passed": report.passed,
            "failures": report.failures,
        },
    ))

    if not report.passed:
        logger.warning(
            "[P7 Supervisor]: step %s (%s) failed per-step verification: %s",
            step.step_id,
            step.capability,
            "; ".join(report.failures) or "(no failure detail)",
        )

    return report.passed or report.status == "UNVERIFIED"


def _run_attribution(
    db: Session,
    plan: "SupervisorPlan",
    wf_step_rows: dict,
    final_report: Optional[dict],
) -> Optional[dict]:
    """
    Phase 30: Run FailureAttributor and persist one FailureAttribution row
    per failed/partial run. Returns the attribution dict for SupervisorResponse.
    """
    try:
        step_reports: dict[str, Optional[str]] = {
            step_id: (wf.verification_json if wf is not None else None)
            for step_id, wf in wf_step_rows.items()
        }
        attribution = failure_attributor.attribute(
            plan=plan,
            step_reports=step_reports,
            final_report=final_report,
        )
        attr_row = FailureAttribution(
            plan_id=plan.plan_id,
            suspect_step_id=attribution.suspect_step_id,
            suspect_capability=attribution.suspect_capability,
            failure_category=attribution.failure_category,
            confidence=attribution.confidence,
            evidence_json=json.dumps(attribution.evidence),
        )
        db.add(attr_row)
        try:
            db.commit()
        except Exception as exc:
            logger.warning("[P30 Attribution]: Failed to persist FailureAttribution: %s", exc)
            db.rollback()
        return attribution.to_dict()
    except Exception as exc:
        logger.warning("[P30 Attribution]: attribution raised unexpectedly: %s", exc)
        return None


class AMOFSupervisor:

    def _dispatch_step(
        self,
        db: Session,
        context: SupervisorContext,
        step: PlanStep,
        resolved_input: dict,
    ) -> tuple[str, Any, bool]:
        """
        Helper method to dispatch a step (original or CDRP replanned step).
        Enforces HITL approval checks cleanly without duplication.
        Returns tuple of (status, result_or_approval_record, approval_guard_bypassed).

        `resolve_user_id()` is called lazily, here, only on the path that
        actually files an Approval -- not by the caller up front. Approval.user_id
        is a real int FK to users.id and must fail loudly on a non-numeric
        owner_id, but owner_id is an opaque tenant string everywhere else in
        the execution layer (Execution.owner_id, WorkflowPlan.owner_id), and
        plenty of real traffic (anything that never touches an approval-gated
        capability) has no numeric owner_id to give.
        """
        approval_bypassed = False
        needs_approval = approval_policy.requires_approval(step.capability)
        if needs_approval and not context.hitl_enabled:
            approval_bypassed = True
            logger.warning(
                "[P7 Supervisor]: HITL disabled for this run; approval gate "
                "bypassed for '%s' (step %s).",
                step.capability,
                step.step_id,
            )
        if needs_approval and context.hitl_enabled:
            user_id_val = context.resolve_user_id()
            workspace_id_val = context.workspace_id
            app_rec = approval_service.create_approval(
                db=db,
                user_id=user_id_val,
                workspace_id=workspace_id_val,
                data=ApprovalCreate(
                    action_type=step.capability,
                    title=f"Approval required for {step.capability.replace('_', ' ')}",
                    description=f"DAG Step {step.step_id} ({step.purpose}) requires user approval before proceeding.",
                    payload=resolved_input,
                    execution_id=context.request_id,
                ),
            )
            return ("WAITING_FOR_APPROVAL", app_rec, approval_bypassed)

        exec_res = supervisor_execution_router.dispatch(
            db=db,
            context=context,
            capability=step.capability,
            resolved_input=resolved_input,
            step_id=step.step_id,
        )
        return (exec_res.status.value, exec_res, approval_bypassed)

    def _persist_routing_decision(self, db: Session, wf_step: WorkflowStep, step_result: Any) -> None:
        """
        Records a RoutingDecisionRecord for `wf_step` if its result carries a
        routing audit dict. Shared by the main execution loop and the CDRP
        replan dispatch path, so a replanned step's routing decision is
        recorded exactly like an original step's -- CDRP-produced steps are
        real steps, not a second-class path exempt from the same audit trail.

        `step_result.get("routing")` rather than `"routing" in step_result`:
        TextGenerationHandler/DocumentSummaryHandler always include a
        "routing" key, but its value is None whenever execution_mode was
        pinned (not "auto"), since no privacy_router.route() call happens for
        a pinned mode. Checking key presence alone crashes on `rdata.get(...)`
        below the moment a pinned-mode step reaches here.
        """
        rdata = step_result.get("routing") if isinstance(step_result, dict) else None
        if not rdata:
            return

        cls_data = rdata.get("classification", {})
        r_rec = RoutingDecisionRecord(
            workflow_step_id=wf_step.id,
            placement=rdata.get("placement", "LOCAL"),
            model=rdata.get("model", "unknown"),
            privacy_label=cls_data.get("label", "PUBLIC") if isinstance(cls_data, dict) else rdata.get("privacy_label", "PUBLIC"),
            classification_confidence=float(cls_data.get("confidence", 1.0)) if isinstance(cls_data, dict) else 1.0,
            classification_stage=cls_data.get("stage") if isinstance(cls_data, dict) else None,
            predicted_quality=float(rdata.get("predicted_quality", 0.0)),
            predicted_latency_ms=float(rdata.get("estimated_latency_ms", 0.0)),
            predicted_cost_usd=float(rdata.get("estimated_cost_usd", 0.0)),
            risk=float(rdata.get("risk", 0.0)),
            routing_confidence=float(rdata.get("routing_confidence", 1.0)),
            constraint_binding=bool(rdata.get("constraint_binding", False)),
            reason=rdata.get("reason"),
        )
        db.add(r_rec)
        try:
            db.commit()
        except Exception as e:
            logger.warning("[P7 Supervisor]: Failed to commit RoutingDecisionRecord: %s", e)
            db.rollback()

    def run(
        self,
        db: Session,
        context: SupervisorContext,
        preset_plan: Optional[SupervisorPlan] = None,
    ) -> SupervisorResponse:
        """
        Main orchestration pipeline for Project 7: AMOF Supervisor Orchestrator.
        1. Analyzes intent (with optional intent_classification P5 execution tracking).
        2. Validates policy boundaries & confidence threshold (0.70).
        3. Generates DAG plan.
        4. Sequentially executes plan steps through P5 Execution Manager.
        5. Aggregates step outputs & citations.
        6. Synthesizes final grounded response via P5 text generation.
        7. Verifies response & executes CDRP replanning if confidence band warrants it.

        `preset_plan` (AMOF-X Phase 8): when given, steps 1-3 (intent
        classification, confidence gate, plan generation) are skipped and
        this plan is used directly -- still re-validated through the same
        `supervisor_policy.validate_dag_plan` gate every other plan source
        goes through (ATGO's decomposer included), and still dispatched
        through the exact same `_dispatch_step`/approval-gate path below.
        This is what lets `run_automation_task` be "just another caller of
        the same orchestration entrypoint" rather than a bypass -- an
        automation that resolves to a side-effecting capability still
        creates a pending Approval and does not auto-execute.
        """
        start_time = time.time()
        execution_ids: list[str] = []
        executed_steps: list[PlanStep] = []
        completed_steps_map: dict[str, PlanStep] = {}
        approval_guard_bypassed = False

        if preset_plan is not None:
            intent = IntentResult(capability="text_generation", confidence=1.0, reason="automation-provided plan (Phase 8)")
            supervisor_policy.validate_dag_plan(preset_plan.steps)
            plan = preset_plan
        else:
            # 1. Intent Analysis
            intent, intent_exec_id = intent_analyzer.analyze(db=db, context=context)
            if intent_exec_id:
                execution_ids.append(intent_exec_id)
                executed_steps.append(
                    PlanStep(
                        step_id="step_intent",
                        capability="text_generation",
                        purpose="intent_classification",
                        depends_on=[],
                        input_template={"question": context.question},
                        status="COMPLETED",
                        execution_id=intent_exec_id,
                        execution_time=0.5,
                    )
                )

            # 2. Policy Validation & Confidence Threshold Check
            is_valid_confidence = supervisor_policy.validate_intent(intent)
            if not is_valid_confidence:
                logger.info(f"[P7 Supervisor]: Intent confidence {intent.confidence} < {settings.SUPERVISOR_INTENT_CONFIDENCE_THRESHOLD}. Requesting clarification.")
                return SupervisorResponse(
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                    status="CLARIFICATION_REQUIRED",
                    intent=intent,
                    answer=(
                        f"I classified your request as '{intent.capability}' with {round(intent.confidence * 100)}% confidence, "
                        "which is below the threshold. Could you please clarify if you want to search indexed documents, query the database, or generate custom text?"
                    ),
                    sources=[],
                    execution_ids=execution_ids,
                    steps=executed_steps,
                    execution_time=round(time.time() - start_time, 2),
                )

            # 3. DAG Plan Generation
            plan = supervisor_planner.build_plan(context=context, intent=intent, db=db)

        # Phase 24: one RunBlackboard per run, constructed here (never a
        # module-level/global instance) now that plan.plan_id -- the run
        # identifier every WorkflowStep below is grouped under -- exists.
        # Scoped to (plan.plan_id, context.owner_id); nothing later in this
        # method can read a different run's or owner's state through it.
        context.blackboard = RunBlackboard(db=db, run_id=plan.plan_id, owner_id=context.owner_id)

        # 3b. Persist WorkflowPlan & initial WorkflowSteps to DB.
        #
        # owner_id is context.owner_id verbatim -- the opaque tenant string
        # every other execution-layer table (Execution.owner_id) already
        # uses, not resolve_user_id()'s strict int. Forcing a numeric id here
        # broke every caller whose owner_id isn't one (see _dispatch_step's
        # docstring); nothing about persisting the plan needs it.
        # max_steps is the configured cap (plan.max_steps, set by the
        # planner from settings.SUPERVISOR_MAX_STEPS), not this particular
        # plan's actual step count -- those are different numbers and the
        # column name says which one this is.
        wf_plan = WorkflowPlan(
            id=plan.plan_id,
            request_id=context.request_id,
            owner_id=context.owner_id,
            max_steps=plan.max_steps,
            status="RUNNING",
        )
        db.add(wf_plan)
        wf_step_rows: dict[str, WorkflowStep] = {}
        for step in plan.steps:
            wf_step = WorkflowStep(
                plan_id=plan.plan_id,
                step_id=step.step_id,
                capability=step.capability,
                depends_on_json=json.dumps(step.depends_on),
                status="PENDING",
            )
            db.add(wf_step)
            wf_step_rows[step.step_id] = wf_step

        try:
            db.commit()
        except Exception as e:
            logger.warning("[P7 Supervisor]: Failed to commit initial WorkflowPlan: %s", e)
            db.rollback()

        # Helper function to execute a single step inside its own DB session
        def _execute_step_in_thread(step_to_exec: PlanStep) -> tuple[PlanStep, str, Any, bool]:
            thread_db = SessionLocal()
            try:
                step_start = time.time()
                step_to_exec.status = "RUNNING"

                resolved_input = supervisor_planner.resolve_step_input(
                    step=step_to_exec,
                    context=context,
                    completed_steps=completed_steps_map,
                )

                event_publisher.publish(Event(
                    event_type=EventType.AGENT_STARTED,
                    owner_id=context.owner_id,
                    trace_id=context.trace_id,
                    payload={"step_id": step_to_exec.step_id, "capability": step_to_exec.capability},
                ))

                disp_status, disp_res, disp_bypassed = self._dispatch_step(
                    db=thread_db,
                    context=context,
                    step=step_to_exec,
                    resolved_input=resolved_input,
                )

                if disp_status != "WAITING_FOR_APPROVAL":
                    exec_res = disp_res
                    step_to_exec.execution_id = exec_res.execution_id
                    step_to_exec.execution_time = exec_res.execution_time

                    if exec_res.status.value == "COMPLETED":
                        step_to_exec.status = "COMPLETED"
                        step_to_exec.result = exec_res.result

                        # Phase 29: verify the output BEFORE it reaches the
                        # blackboard or counts as completed -- a failed output
                        # must not poison downstream agents reading $state.*
                        # or typed bindings. Deliberately after the pre-write
                        # status commit so a mid-verification crash leaves a
                        # RUNNING row, not a COMPLETED row whose result was
                        # never trusted.
                        verification_passed = _verify_completed_step(
                            db=thread_db,
                            context=context,
                            plan_id=plan.plan_id,
                            step=step_to_exec,
                            resolved_input=resolved_input,
                        )
                        if verification_passed:
                            _write_step_to_blackboard(
                                context, step_to_exec.step_id, step_to_exec.capability, step_to_exec.result, db_sess=thread_db
                            )
                        else:
                            # Mark the step FAILED so the scheduler's
                            # dependents get BLOCKED (mark_blocked) and the
                            # failed_step branch below reports it; the result
                            # is dropped, never written to the blackboard.
                            logger.warning(
                                "[P7 Supervisor]: step %s output failed verification; "
                                "blocking its dependents.",
                                step_to_exec.step_id,
                            )
                            step_to_exec.status = "FAILED"
                            step_to_exec.result = None

                    else:
                        step_to_exec.status = exec_res.status.value

                    event_publisher.publish(Event(
                        event_type=EventType.AGENT_COMPLETED,
                        owner_id=context.owner_id,
                        trace_id=context.trace_id,
                        payload={"step_id": step_to_exec.step_id, "capability": step_to_exec.capability, "status": step_to_exec.status},
                    ))

                    wf_step = thread_db.query(WorkflowStep).filter(
                        WorkflowStep.plan_id == plan.plan_id,
                        WorkflowStep.step_id == step_to_exec.step_id,
                    ).first()
                    if wf_step:
                        # Phase 29: the per-step report must survive even when
                        # the status commit cannot (e.g. execution_id is an
                        # Execution FK that doesn't resolve -- which a real
                        # dispatch always satisfies). Read the persisted report
                        # back from verification_json, which
                        # _verify_completed_step wrote under its own commit,
                        # and reuse it instead of re-running the verifier.
                        persisted_report: Optional[dict] = None
                        try:
                            persisted_report = json.loads(wf_step.verification_json) if wf_step.verification_json else None
                        except (TypeError, ValueError):
                            persisted_report = None

                        wf_step.status = step_to_exec.status
                        wf_step.execution_id = step_to_exec.execution_id
                        wf_step.execution_time = step_to_exec.execution_time
                        if step_to_exec.result is not None:
                            wf_step.result_json = json.dumps(step_to_exec.result)
                        try:
                            thread_db.commit()
                        except Exception as e:
                            logger.warning("[P7 Supervisor]: Failed to commit step %s status: %s", step_to_exec.step_id, e)
                            thread_db.rollback()
                            # Fallback commit of the load-bearing fields only,
                            # so verification_json/status survive even when the
                            # full status commit is rejected.
                            try:
                                if persisted_report is not None:
                                    wf_step.verification_json = json.dumps(persisted_report)
                                wf_step.status = step_to_exec.status
                                thread_db.commit()
                            except Exception as e2:
                                logger.warning(
                                    "[P7 Supervisor]: Fallback verification_json commit for step %s failed: %s",
                                    step_to_exec.step_id, e2,
                                )
                                thread_db.rollback()

                        self._persist_routing_decision(thread_db, wf_step, step_to_exec.result)

                return (step_to_exec, disp_status, disp_res, disp_bypassed)
            finally:
                thread_db.close()

        # 4. DAG Step Execution Loop
        while any(s.status == "PENDING" for s in plan.steps):
            ready = DagScheduler.ready_steps(plan.steps)
            if not ready:
                DagScheduler.detect_deadlock(plan.steps)

            plan_order = {s.step_id: i for i, s in enumerate(plan.steps)}
            ready.sort(key=lambda s: plan_order[s.step_id])

            use_parallel = settings.SUPERVISOR_PARALLEL_ENABLED and len(ready) > 1

            if use_parallel:
                max_workers = min(len(ready), settings.SUPERVISOR_MAX_PARALLEL_STEPS)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [executor.submit(_execute_step_in_thread, step) for step in ready]
                    results = [f.result() for f in futures]
            else:
                results = [_execute_step_in_thread(step) for step in ready]

            results.sort(key=lambda r: plan_order[r[0].step_id])

            for step, disp_status, disp_res, disp_bypassed in results:
                if disp_bypassed:
                    approval_guard_bypassed = True

                if disp_status == "WAITING_FOR_APPROVAL":
                    app_rec = disp_res
                    step.status = "WAITING_FOR_APPROVAL"
                    executed_steps.append(step)

                    wf_step = wf_step_rows.get(step.step_id)
                    if wf_step:
                        wf_step.status = "WAITING_FOR_APPROVAL"
                    wf_plan.status = "WAITING_FOR_APPROVAL"
                    try:
                        db.commit()
                    except Exception as e:
                        db.rollback()

                    logger.info(f"[P7 Supervisor]: Paused execution for HITL Approval #{app_rec.id} (action: {step.capability})")
                    return SupervisorResponse(
                        request_id=context.request_id,
                        trace_id=context.trace_id,
                        status="WAITING_FOR_APPROVAL",
                        intent=intent,
                        answer=(
                            f"Action '{step.capability}' requires Human-in-the-Loop approval before execution. "
                            f"Approval record #{app_rec.id} has been created and is waiting for your review."
                        ),
                        sources=[],
                        execution_ids=execution_ids,
                        steps=executed_steps,
                        execution_time=round(time.time() - start_time, 2),
                        approval_id=app_rec.id,
                    )

                if step.execution_id and step.execution_id not in execution_ids:
                    execution_ids.append(step.execution_id)

                if step.status == "COMPLETED":
                    completed_steps_map[step.step_id] = step
                else:
                    blocked_ids = DagScheduler.mark_blocked(plan.steps, step.step_id)
                    plan_map = {s.step_id: s for s in plan.steps}
                    for b_id in blocked_ids:
                        b_step = plan_map.get(b_id)
                        if b_step and b_step not in executed_steps:
                            executed_steps.append(b_step)
                        b_wf = wf_step_rows.get(b_id)
                        if b_wf:
                            b_wf.status = "BLOCKED"
                            b_wf.blocked_by_step_id = step.step_id
                            try:
                                db.commit()
                            except Exception:
                                db.rollback()

                if step not in executed_steps:
                    executed_steps.append(step)

        completed_count = sum(1 for s in plan.steps if s.status == "COMPLETED")
        failed_steps = [s for s in plan.steps if s.status in ("FAILED", "TIMEOUT")]
        blocked_steps = [s for s in plan.steps if s.status == "BLOCKED"]

        if failed_steps or blocked_steps:
            if completed_count > 0:
                wf_plan.status = "PARTIAL"
                try:
                    db.commit()
                except Exception as e:
                    db.rollback()

                aggregated_data, sources = result_aggregator.aggregate(executed_steps)
                answer_text, synth_exec_id = response_synthesizer.synthesize(
                    db=db,
                    context=context,
                    aggregated_data=aggregated_data,
                    sources=sources,
                )
                if synth_exec_id:
                    execution_ids.append(synth_exec_id)

                failed_info = []
                for s in failed_steps:
                    b_list = [b.step_id for b in blocked_steps if b.blocked_by_step_id == s.step_id]
                    if b_list:
                        failed_info.append(f"step '{s.step_id}' ({s.capability}) failed, blocking {b_list}")
                    else:
                        failed_info.append(f"step '{s.step_id}' ({s.capability}) failed")

                branch_msg = "; ".join(failed_info)
                partial_answer = f"{answer_text}\n\n[Partial Execution Notice]: Failed branch details: {branch_msg}."

                return SupervisorResponse(
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                    status="PARTIAL",
                    intent=intent,
                    answer=partial_answer,
                    sources=sources,
                    execution_ids=execution_ids,
                    steps=executed_steps,
                    execution_time=round(time.time() - start_time, 2),
                    attribution=_run_attribution(
                        db=db,
                        plan=plan,
                        wf_step_rows=wf_step_rows,
                        final_report=None,
                    ),
                )
            else:
                wf_plan.status = "FAILED"
                try:
                    db.commit()
                except Exception as e:
                    db.rollback()

                failed_info = [f"'{s.step_id}' ({s.capability})" for s in failed_steps]
                return SupervisorResponse(
                    request_id=context.request_id,
                    trace_id=context.trace_id,
                    status="FAILED",
                    intent=intent,
                    answer=f"One or more prerequisite execution steps failed: {', '.join(failed_info)}. Please review execution trace details.",
                    sources=[],
                    execution_ids=execution_ids,
                    steps=executed_steps,
                    execution_time=round(time.time() - start_time, 2),
                    attribution=_run_attribution(
                        db=db,
                        plan=plan,
                        wf_step_rows=wf_step_rows,
                        final_report=None,
                    ),
                )

        # 5. Result Aggregation
        aggregated_data, sources = result_aggregator.aggregate(executed_steps)

        # 6. Response Synthesis
        answer_text, synth_exec_id = response_synthesizer.synthesize(
            db=db,
            context=context,
            aggregated_data=aggregated_data,
            sources=sources,
        )

        if synth_exec_id:
            execution_ids.append(synth_exec_id)
            executed_steps.append(
                PlanStep(
                    step_id="step_synthesis",
                    capability="text_generation",
                    purpose="synthesis",
                    depends_on=[s.step_id for s in plan.steps if s.status == "COMPLETED"],
                    input_template={},
                    status="COMPLETED",
                    execution_id=synth_exec_id,
                    execution_time=0.5,
                )
            )

        # 7. Verification & CDRP Replanning Loop
        verification_payload = None
        replan_count = 0
        # Every capability substituted into this chain so far (Phase 10
        # oscillation fix) -- passed to cdrp_replanner.replan() so a low-band
        # substitution can never revisit one, which is what previously let
        # rag_answer and text_generation ping-pong back and forth instead of
        # converging or escalating.
        cdrp_tried_capabilities: set[str] = set()
        # Phase 29: the whole-answer verifier is the final gate in every mode
        # except "off" -- per_step supplements it, final_only reproduces
        # today's behavior exactly, and off skips it (the configured
        # "off -- also skips final-answer verifier" contract).
        final_gate_enabled = verification_mode_for_run(context) != "off"
        if final_gate_enabled and context.verification_enabled:
            while True:
                report = response_verifier.verify(
                    answer=answer_text,
                    aggregated_data=aggregated_data,
                    sources=sources,
                )
                verification_payload = report.to_dict()
                band = report.confidence_band

                event_publisher.publish(Event(
                    event_type=EventType.VERIFICATION_COMPLETED,
                    owner_id=context.owner_id,
                    trace_id=context.trace_id,
                    payload={"confidence": report.confidence, "band": band, "passed": report.passed},
                ))

                # confidence_band only ever returns "critical"|"low"|"high"|
                # "medium" (see VerificationReport.confidence_band) -- the
                # "medium and cap reached" half of this is also re-checked
                # just below inside the (medium, low) branch; kept here too
                # so the loop exits immediately without an extra iteration.
                if band == "high" or (band == "medium" and replan_count >= settings.CDRP_MAX_REPLANS):
                    break

                if not report.passed:
                    logger.info(
                        "[P7 Supervisor]: verification failed (confidence %.2f, band '%s'): %s",
                        report.confidence,
                        band,
                        "; ".join(report.failures),
                    )

                if band in ("medium", "low"):
                    if replan_count >= settings.CDRP_MAX_REPLANS:
                        logger.warning("[P7 Supervisor]: Replan cap reached (%d). Stopping replanning loop.", replan_count)
                        break

                    # Phase 30: use FailureAttributor instead of the blunt
                    # steps[-1] proxy (Phase 4 documented limitation).
                    step_reports_inner: dict[str, Optional[str]] = {
                        sid: (wf.verification_json if wf is not None else None)
                        for sid, wf in wf_step_rows.items()
                    }
                    attribution = failure_attributor.attribute(
                        plan=plan,
                        step_reports=step_reports_inner,
                        final_report=report.to_dict(),
                    )
                    plan_map_inner = {s.step_id: s for s in plan.steps}
                    attributed_step = plan_map_inner.get(attribution.suspect_step_id)
                    # Fall back to last step only for synthesis attribution or unknown
                    if attributed_step is None or attribution.suspect_step_id in (
                        "step_synthesis", "unknown"
                    ):
                        attributed_step = plan.steps[-1] if plan.steps else None
                    last_step = attributed_step
                    if not last_step:
                        break

                    cdrp_tried_capabilities.add(last_step.capability)
                    replan_step, replan_event = cdrp_replanner.replan(
                        db=db,
                        context=context,
                        plan=plan,
                        failed_step=last_step,
                        report=report,
                        replan_count=replan_count,
                        tried_capabilities=cdrp_tried_capabilities,
                    )

                    if not replan_step:
                        break

                    cdrp_tried_capabilities.add(replan_step.capability)
                    replan_count += 1

                    orig_wf_id = wf_step_rows[last_step.step_id].id if last_step.step_id in wf_step_rows else None
                    new_wf_step = WorkflowStep(
                        plan_id=plan.plan_id,
                        step_id=replan_step.step_id,
                        capability=replan_step.capability,
                        depends_on_json=json.dumps(replan_step.depends_on),
                        status="RUNNING",
                        replanning_of=orig_wf_id,
                    )
                    db.add(new_wf_step)
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()

                    wf_step_rows[replan_step.step_id] = new_wf_step

                    if replan_event:
                        replan_event.new_step_id = new_wf_step.id
                        try:
                            db.commit()
                        except Exception:
                            db.rollback()

                    resolved_replan_input = supervisor_planner.resolve_step_input(
                        step=replan_step,
                        context=context,
                        completed_steps=completed_steps_map,
                    )

                    event_publisher.publish(Event(
                        event_type=EventType.AGENT_STARTED,
                        owner_id=context.owner_id,
                        trace_id=context.trace_id,
                        payload={"step_id": replan_step.step_id, "capability": replan_step.capability, "replan_of": last_step.step_id},
                    ))

                    disp_status, disp_res, disp_bypassed = self._dispatch_step(
                        db=db,
                        context=context,
                        step=replan_step,
                        resolved_input=resolved_replan_input,
                    )
                    if disp_bypassed:
                        approval_guard_bypassed = True

                    if disp_status == "WAITING_FOR_APPROVAL":
                        replan_step.status = "WAITING_FOR_APPROVAL"
                        new_wf_step.status = "WAITING_FOR_APPROVAL"
                        wf_plan.status = "WAITING_FOR_APPROVAL"
                        try:
                            db.commit()
                        except Exception:
                            db.rollback()

                        return SupervisorResponse(
                            request_id=context.request_id,
                            trace_id=context.trace_id,
                            status="WAITING_FOR_APPROVAL",
                            intent=intent,
                            answer=f"Replanned step '{replan_step.capability}' requires approval.",
                            sources=[],
                            execution_ids=execution_ids,
                            steps=executed_steps,
                            execution_time=round(time.time() - start_time, 2),
                            approval_id=disp_res.id if hasattr(disp_res, "id") else None,
                        )

                    exec_res = disp_res
                    replan_step.execution_id = exec_res.execution_id
                    replan_step.execution_time = exec_res.execution_time
                    execution_ids.append(exec_res.execution_id)

                    if exec_res.status.value == "COMPLETED":
                        replan_step.status = "COMPLETED"
                        replan_step.result = exec_res.result

                        # Phase 29: same before-the-blackboard gate as the
                        # main loop -- a replanned step is a real step, not a
                        # second-class one exempt from verification.
                        verification_passed = _verify_completed_step(
                            db=db,
                            context=context,
                            plan_id=plan.plan_id,
                            step=replan_step,
                            resolved_input=resolved_replan_input,
                        )
                        if verification_passed:
                            replan_step.status = "COMPLETED"
                            completed_steps_map[replan_step.step_id] = replan_step
                            _write_step_to_blackboard(context, replan_step.step_id, replan_step.capability, replan_step.result)
                            new_wf_step.status = "COMPLETED"
                            new_wf_step.execution_id = exec_res.execution_id
                            new_wf_step.execution_time = exec_res.execution_time
                            if exec_res.result:
                                new_wf_step.result_json = json.dumps(exec_res.result)
                        else:
                            replan_step.status = "FAILED"
                            replan_step.result = None
                            new_wf_step.status = "FAILED"
                            logger.warning(
                                "[P7 Supervisor]: replanned step %s output failed "
                                "verification; recorded FAILED, not completed.",
                                replan_step.step_id,
                            )
                    else:
                        replan_step.status = exec_res.status.value
                        new_wf_step.status = exec_res.status.value

                    event_publisher.publish(Event(
                        event_type=EventType.AGENT_COMPLETED,
                        owner_id=context.owner_id,
                        trace_id=context.trace_id,
                        payload={"step_id": replan_step.step_id, "capability": replan_step.capability, "status": replan_step.status},
                    ))

                    try:
                        db.commit()
                    except Exception:
                        db.rollback()

                    self._persist_routing_decision(db, new_wf_step, replan_step.result)

                    executed_steps.append(replan_step)
                    plan.steps.append(replan_step)

                    aggregated_data, sources = result_aggregator.aggregate(executed_steps)
                    answer_text, synth_exec_id = response_synthesizer.synthesize(
                        db=db,
                        context=context,
                        aggregated_data=aggregated_data,
                        sources=sources,
                    )
                    if synth_exec_id:
                        execution_ids.append(synth_exec_id)

                elif band == "critical":
                    logger.warning("[P7 Supervisor]: Escalating critical verification outcome.")
                    break

        wf_plan.status = "COMPLETED"
        try:
            db.commit()
        except Exception as e:
            logger.warning("[P7 Supervisor]: Failed to update wf_plan.status to COMPLETED: %s", e)
            db.rollback()

        return SupervisorResponse(
            request_id=context.request_id,
            trace_id=context.trace_id,
            status="COMPLETED",
            intent=intent,
            answer=answer_text,
            sources=sources,
            execution_ids=execution_ids,
            steps=executed_steps,
            execution_time=round(time.time() - start_time, 2),
            verification=verification_payload,
            approval_guard_bypassed=approval_guard_bypassed,
        )


amof_supervisor = AMOFSupervisor()
