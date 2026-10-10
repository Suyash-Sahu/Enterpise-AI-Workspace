from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class ExecutionStatus(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    CANCELLED = "CANCELLED"


class ExecutionRequest(BaseModel):
    task_type: str = Field(..., description="Capability task name (rag_search, rag_answer, database_query, text_generation, document_summary)", json_schema_extra={"example": "rag_answer"})
    input: dict[str, Any] = Field(..., description="Task payload input object")
    execution_mode: Optional[str] = Field(default="auto", description="Execution mode: auto, local, cloud")
    idempotency_key: Optional[str] = Field(default=None, description="Optional idempotency key to prevent duplicate execution")
    request_id: Optional[str] = Field(default=None, description="Correlation / trace ID for observability")
    timeout: Optional[float] = Field(default=None, description="Custom execution timeout in seconds")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Custom task metadata")
    approval_id: Optional[int] = Field(
        default=None,
        description=(
            "Required when task_type is a capability marked "
            "requires_human_approval=True (app/execution/contracts.py's "
            "CapabilityMetadata). The executor claims this approval "
            "atomically (Approval.status APPROVED -> EXECUTING) before "
            "dispatching the handler, and uses the approved/edited payload "
            "from the approval record rather than `input` above -- the same "
            "invariant app/api/connectors.py's gmail/send endpoint already "
            "enforces, generalized to every side-effecting capability."
        ),
    )


class ExecutionResponse(BaseModel):
    execution_id: str
    status: ExecutionStatus
    task_type: str
    result: Optional[dict[str, Any]] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    idempotency_key: Optional[str] = None
    request_id: Optional[str] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class ExecutionStatusResponse(BaseModel):
    execution_id: str
    status: ExecutionStatus
    task_type: str
    execution_mode: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time: float = 0.0
    retry_count: int = 0
    error_message: Optional[str] = None


class ExecutionHistoryResponse(BaseModel):
    total: int
    items: list[ExecutionResponse]
