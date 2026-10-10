from datetime import datetime
from typing import Optional, Any, Literal
from pydantic import BaseModel, Field


class ApprovalCreate(BaseModel):
    action_type: str = Field(..., description="Target side-effect action, e.g., gmail.send, calendar.create", json_schema_extra={"example": "gmail.send"})
    title: str = Field(..., description="Human-readable title describing proposed action", json_schema_extra={"example": "Send meeting postponement email"})
    description: Optional[str] = Field(default=None, description="Detailed explanation of proposed side-effect action")
    payload: dict[str, Any] = Field(..., description="Action parameters dictionary")
    risk_level: Literal["low", "medium", "high", "critical"] = Field(default="high", description="Assessed risk level")
    execution_id: Optional[str] = Field(default=None, description="Associated P7/P5 Execution ID")


class ApprovalEdit(BaseModel):
    edited_payload: dict[str, Any] = Field(..., description="Modified action parameters dictionary")


class ApprovalReject(BaseModel):
    reason: Optional[str] = Field(default=None, description="Reason rationale for rejecting the action")


class ApprovalResponse(BaseModel):
    id: int = Field(..., description="Approval record ID")
    user_id: int = Field(..., description="Owner User ID")
    workspace_id: str = Field(..., description="Tenant workspace ID")
    execution_id: Optional[str] = Field(default=None, description="Associated execution ID")
    action_type: str = Field(..., description="Side-effect action type")
    status: Literal["pending", "approved", "edited", "rejected", "executing", "completed", "failed", "expired"] = Field(..., description="Approval lifecycle status")
    title: str = Field(..., description="Approval title")
    description: Optional[str] = Field(default=None)
    payload: dict[str, Any] = Field(..., description="Original action payload")
    edited_payload: Optional[dict[str, Any]] = Field(default=None, description="User-modified action payload")
    effective_payload: dict[str, Any] = Field(..., description="Resolved execution payload (edited_payload or payload)")
    risk_level: str = Field(..., description="Risk level")
    expires_at: datetime = Field(..., description="Approval expiration timestamp")
    approved_at: Optional[datetime] = Field(default=None)
    rejected_at: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class ApprovalPendingListResponse(BaseModel):
    items: list[ApprovalResponse] = Field(default_factory=list)
    total: int = Field(default=0)


class ApprovalEventResponse(BaseModel):
    id: int = Field(..., description="Event log ID")
    approval_id: int = Field(..., description="Associated Approval ID")
    user_id: int = Field(..., description="Actor User ID")
    event_type: str = Field(..., description="Lifecycle event type")
    old_status: Optional[str] = Field(default=None)
    new_status: str = Field(..., description="New status")
    metadata_json: Optional[dict[str, Any]] = Field(default=None)
    created_at: datetime = Field(...)


class ApprovalHealthResponse(BaseModel):
    status: str = Field(..., description="P8 operational status")
    approvals_enabled: bool = Field(default=True)
    default_ttl_minutes: int = Field(default=60)
    max_ttl_minutes: int = Field(default=1440)
    auto_expire_enabled: bool = Field(default=True)
