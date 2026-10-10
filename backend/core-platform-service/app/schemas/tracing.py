"""
Traceability schemas (AMOF-X Phase 10).
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class StepTraceDTO(BaseModel):
    step_id: str
    capability: str
    depends_on: List[str]
    status: str
    execution_id: Optional[str] = None
    replanning_of: Optional[str] = None
    execution_time: float = 0.0
    created_at: Optional[datetime] = None


class PlanTraceDTO(BaseModel):
    plan_id: str
    request_id: str
    owner_id: str
    status: str
    max_steps: int
    steps: List[StepTraceDTO]
    created_at: Optional[datetime] = None


class RoutingDecisionTraceDTO(BaseModel):
    id: str
    workflow_step_id: str
    placement: str
    model: str
    privacy_label: str
    classification_confidence: float
    predicted_quality: float
    predicted_latency_ms: float
    predicted_cost_usd: float
    routing_confidence: float
    reason: Optional[str] = None


class ReplanningEventTraceDTO(BaseModel):
    id: str
    original_step_id: str
    new_step_id: Optional[str] = None
    reason: str
    confidence_before: float
    confidence_after: Optional[float] = None
    created_at: Optional[datetime] = None


class ExecutionTraceDTO(BaseModel):
    execution_id: str
    task_type: str
    status: str
    provider: Optional[str] = None
    model: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None


class ApprovalTraceDTO(BaseModel):
    approval_id: int
    action_type: str
    status: str
    risk_level: str
    title: str
    created_at: Optional[datetime] = None


class TraceViewResponse(BaseModel):
    trace_id: str
    owner_id: str
    plan: Optional[PlanTraceDTO] = None
    routing_decisions: List[RoutingDecisionTraceDTO] = []
    replanning_events: List[ReplanningEventTraceDTO] = []
    executions: List[ExecutionTraceDTO] = []
    approvals: List[ApprovalTraceDTO] = []
    total_latency_ms: float = 0.0
