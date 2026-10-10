"""
TraceView Aggregator Service (AMOF-X Phase 10).

Aggregates structured execution history, workflow steps, privacy routing decisions,
CDRP replanning events, and approval lifecycle records associated with a trace_id.
"""
import json
import logging
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.workflow import WorkflowPlan, ReplanningEvent
from app.models.routing_decision import RoutingDecisionRecord
from app.models.execution import Execution
from app.models.approval import Approval
from app.schemas.tracing import (
    TraceViewResponse,
    PlanTraceDTO,
    StepTraceDTO,
    RoutingDecisionTraceDTO,
    ReplanningEventTraceDTO,
    ExecutionTraceDTO,
    ApprovalTraceDTO,
)

logger = logging.getLogger(__name__)


class TraceViewService:

    @staticmethod
    def get_trace(db: Session, trace_id: str, owner_id: str) -> TraceViewResponse:
        """
        Aggregates all telemetry records for a given trace_id (request_id, plan_id, or execution_id)
        with strict tenant isolation.
        """
        # 1. Search for WorkflowPlan matching trace_id as plan_id or request_id
        # request_id is caller-supplied and not unique, so more than one plan
        # can match it (retries, or the same id reused later) -- order_by
        # makes "the most recent one" a deterministic choice instead of
        # whatever order Postgres happens to return.
        plan_record = db.query(WorkflowPlan).filter(
            (WorkflowPlan.id == trace_id) | (WorkflowPlan.request_id == trace_id),
            WorkflowPlan.owner_id == str(owner_id),
        ).order_by(WorkflowPlan.created_at.desc()).first()

        plan_dto: Optional[PlanTraceDTO] = None
        step_ids: list[str] = []
        execution_ids: set[str] = set()

        if plan_record:
            steps_dtos: list[StepTraceDTO] = []
            for s in plan_record.steps:
                step_ids.append(s.id)
                if s.execution_id:
                    execution_ids.add(s.execution_id)
                try:
                    deps = json.loads(s.depends_on_json or "[]")
                except Exception:
                    deps = []

                steps_dtos.append(
                    StepTraceDTO(
                        step_id=s.step_id,
                        capability=s.capability,
                        depends_on=deps,
                        status=s.status,
                        execution_id=s.execution_id,
                        replanning_of=s.replanning_of,
                        execution_time=s.execution_time,
                        created_at=s.created_at,
                    )
                )

            plan_dto = PlanTraceDTO(
                plan_id=plan_record.id,
                request_id=plan_record.request_id,
                owner_id=plan_record.owner_id,
                status=plan_record.status,
                max_steps=plan_record.max_steps,
                steps=steps_dtos,
                created_at=plan_record.created_at,
            )

        # 2. Query RoutingDecisionRecords for plan steps
        routing_dtos: list[RoutingDecisionTraceDTO] = []
        if step_ids:
            rdec_records = db.query(RoutingDecisionRecord).filter(
                RoutingDecisionRecord.workflow_step_id.in_(step_ids)
            ).all()

            for rd in rdec_records:
                routing_dtos.append(
                    RoutingDecisionTraceDTO(
                        id=rd.id,
                        workflow_step_id=rd.workflow_step_id,
                        placement=rd.placement,
                        model=rd.model,
                        privacy_label=rd.privacy_label,
                        classification_confidence=rd.classification_confidence,
                        predicted_quality=rd.predicted_quality,
                        predicted_latency_ms=rd.predicted_latency_ms,
                        predicted_cost_usd=rd.predicted_cost_usd,
                        routing_confidence=rd.routing_confidence,
                        reason=rd.reason,
                    )
                )

        # 3. Query ReplanningEvents for plan steps
        replan_dtos: list[ReplanningEventTraceDTO] = []
        if step_ids:
            replan_records = db.query(ReplanningEvent).filter(
                (ReplanningEvent.original_step_id.in_(step_ids)) |
                (ReplanningEvent.new_step_id.in_(step_ids))
            ).all()

            for rp in replan_records:
                replan_dtos.append(
                    ReplanningEventTraceDTO(
                        id=rp.id,
                        original_step_id=rp.original_step_id,
                        new_step_id=rp.new_step_id,
                        reason=rp.reason,
                        confidence_before=rp.confidence_before,
                        confidence_after=rp.confidence_after,
                        created_at=rp.created_at,
                    )
                )

        # 4. Query Execution records matching trace_id as request_id/id or linked step execution_ids
        exec_query = db.query(Execution).filter(
            Execution.owner_id == str(owner_id),
            (
                (Execution.request_id == trace_id) |
                (Execution.id == trace_id) |
                (Execution.id.in_(list(execution_ids)) if execution_ids else False)
            ),
        )
        exec_records = exec_query.all()

        exec_dtos: list[ExecutionTraceDTO] = []
        total_latency_ms = 0.0

        for ex in exec_records:
            execution_ids.add(ex.id)
            total_latency_ms += (ex.execution_time or 0.0) * 1000.0
            exec_dtos.append(
                ExecutionTraceDTO(
                    execution_id=ex.id,
                    task_type=ex.task_type,
                    status=ex.status,
                    provider=ex.provider,
                    model=ex.model,
                    execution_time=ex.execution_time or 0.0,
                    retry_count=ex.retry_count or 0,
                    error_message=ex.error_message,
                    created_at=ex.created_at,
                )
            )

        # 5. Query Approvals associated with the executions or trace
        approval_dtos: list[ApprovalTraceDTO] = []
        try:
            user_id_int = int(owner_id)
            approval_records = db.query(Approval).filter(
                Approval.user_id == user_id_int,
                (
                    (Approval.execution_id.in_(list(execution_ids)) if execution_ids else False)
                ),
            ).all()

            for ap in approval_records:
                approval_dtos.append(
                    ApprovalTraceDTO(
                        approval_id=ap.id,
                        action_type=ap.action_type,
                        status=ap.status,
                        risk_level=ap.risk_level,
                        title=ap.title,
                        created_at=ap.created_at,
                    )
                )
        except (ValueError, TypeError):
            pass

        if not plan_dto and not exec_dtos:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trace '{trace_id}' not found or access denied",
            )

        return TraceViewResponse(
            trace_id=trace_id,
            owner_id=str(owner_id),
            plan=plan_dto,
            routing_decisions=routing_dtos,
            replanning_events=replan_dtos,
            executions=exec_dtos,
            approvals=approval_dtos,
            total_latency_ms=round(total_latency_ms, 2),
        )


trace_view_service = TraceViewService()
