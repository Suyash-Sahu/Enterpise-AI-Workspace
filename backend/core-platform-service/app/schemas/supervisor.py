from typing import Optional, Any, Literal
from pydantic import BaseModel, Field


class SupervisorRequest(BaseModel):
    question: str = Field(..., description="User prompt or query for AMOF Supervisor orchestration", json_schema_extra={"example": "How many documents do I have indexed?"})
    execution_mode: Optional[str] = Field(default="auto", description="Desired execution mode: local, cloud, auto")
    timeout: Optional[float] = Field(default=60.0, description="Supervisor orchestration timeout limit in seconds")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Task context metadata")
    conversation_id: Optional[str] = Field(default=None, description="Optional conversation trace thread ID")


class IntentResult(BaseModel):
    capability: Literal[
        "rag_search",
        "rag_answer",
        "database_query",
        "text_generation",
        "document_summary",
    ] = Field(..., description="Resolved target capability")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Intent classification confidence score (0.0 to 1.0)")
    reason: str = Field(default="", description="Explanation rationale for intent classification")


class PlanStep(BaseModel):
    step_id: str = Field(..., description="Unique step identifier in the DAG execution graph")
    capability: str = Field(..., description="Underlying capability module invoked")
    purpose: Literal["capability", "intent_classification", "synthesis"] = Field(default="capability", description="Step execution purpose annotation")
    depends_on: list[str] = Field(default_factory=list, description="Prerequisite step IDs")
    input_template: dict[str, Any] = Field(default_factory=dict, description="Structured input parameter template with allowlisted $step.* references")
    input_bindings: dict[str, str] = Field(
        default_factory=dict,
        description=(
            "Phase 25: typed, field-level handoffs. Maps a consumer input "
            "field name to a producer reference of the form "
            "'$step.<step_id>.output.<dotted.path>', resolved against the "
            "producer capability's declared Agent output schema and checked "
            "for compatibility with this step's capability's declared Agent "
            "input schema at plan-validation time (see "
            "app/supervisor/policies.py::validate_dag_plan and "
            "app/agents/handoff.py). Distinct from input_template's untyped "
            "'$step.<id>.result' form, which this does not replace."
        ),
    )
    status: str = Field(default="PENDING", description="Step execution status (PENDING, RUNNING, COMPLETED, FAILED, TIMEOUT, BLOCKED)")
    blocked_by_step_id: Optional[str] = Field(default=None, description="Step ID that caused this step to be blocked")
    execution_id: Optional[str] = Field(default=None, description="Associated P5 Execution ID")
    result: Optional[dict[str, Any]] = Field(default=None, description="Execution step output payload")
    execution_time: float = Field(default=0.0, description="Step duration in seconds")


class SupervisorPlan(BaseModel):
    plan_id: str = Field(..., description="Unique execution plan ID")
    request_id: str = Field(..., description="Trace request ID")
    steps: list[PlanStep] = Field(default_factory=list, description="Ordered DAG execution steps")
    max_steps: int = Field(default=5, description="Maximum allowed steps limit")
    decomposer_version: Optional[str] = Field(
        default=None,
        description=(
            "Version tag of the ATGO decomposer that produced this plan's "
            "steps (see app/supervisor/decomposer.py), or None when the plan "
            "came from the fixed single-capability planner instead. Persisted "
            "per-plan so 'with ATGO' vs 'fixed planner' is a real ablation "
            "axis, not an inferred one."
        ),
    )


class SupervisorResponse(BaseModel):
    request_id: str = Field(..., description="Trace request ID")
    trace_id: str = Field(..., description="Correlation trace ID across P1-P8")
    status: str = Field(..., description="Supervisor run status (COMPLETED, FAILED, PARTIAL, TIMEOUT, CLARIFICATION_REQUIRED, REJECTED, WAITING_FOR_APPROVAL)")
    intent: IntentResult = Field(..., description="Resolved intent classification")
    answer: str = Field(..., description="Synthesized grounded answer or clarification message")
    sources: list[dict[str, Any]] = Field(default_factory=list, description="Attributed document citations or SQL trace metadata")
    execution_ids: list[str] = Field(default_factory=list, description="P5 execution record IDs created during run")
    steps: list[PlanStep] = Field(default_factory=list, description="Executed plan steps with telemetry")
    execution_time: float = Field(default=0.0, description="Total supervisor run time in seconds")
    approval_id: Optional[int] = Field(default=None, description="Created pending approval ID if HITL approval required")
    verification: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Verification report for the synthesized answer: status, confidence, "
            "the individual checks applied and any failures. None when "
            "verification was disabled for the run."
        ),
    )
    approval_guard_bypassed: bool = Field(
        default=False,
        description=(
            "True when a step required HITL approval but the gate was disabled "
            "for this run. Recorded so the HITL ablation arm is measurable "
            "rather than silent."
        ),
    )
    attribution: Optional[dict] = Field(
        default=None,
        description=(
            "Phase 30: Failure attribution record. For failed or partial runs, "
            "identifies the suspect step, failure category from the closed "
            "taxonomy (no_data, wrong_data, unsupported_claim, handoff_mismatch, "
            "capability_misselected, tool_error, timeout, "
            "injection_attempt_detected), confidence score, and evidence chain. "
            "None on successful runs."
        ),
    )


class SupervisorHealthResponse(BaseModel):
    status: str = Field(..., description="Supervisor operational status")
    supervisor_enabled: bool = Field(default=True)
    p5_available: bool = Field(default=True)
    supported_capabilities: list[str] = Field(default_factory=list)
    max_steps: int = Field(default=5)
    max_timeout_seconds: float = Field(default=120.0)
