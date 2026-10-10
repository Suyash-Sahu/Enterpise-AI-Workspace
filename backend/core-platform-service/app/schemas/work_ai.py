"""AMOF Work AI layer API schemas. owner_id is deliberately never exposed or accepted."""
from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

AutonomyLevel = Literal["L0", "L1", "L2", "L3"]
MutatingKind = Literal["create_item", "update_item", "link_items"]


class ProposalResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    kind: str
    agent: str
    payload: dict[str, Any]
    source: str
    source_ref: Optional[str] = None
    status: str
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    privacy_tier: Optional[str] = None
    autonomy_level: str
    approval_id: Optional[int] = None
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    created_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    decided_by: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ProposalDecision(BaseModel):
    # Only whitelisted, non-scope fields are honoured (see pipeline._EDITABLE).
    edited_payload: Optional[dict[str, Any]] = None
    reason: Optional[str] = Field(default=None, max_length=500)


class KillSwitchRequest(BaseModel):
    enabled: bool
    project_id: Optional[str] = None  # None == the user-level ("org-level") switch


class AutonomyRequest(BaseModel):
    project_id: str = Field(min_length=1)
    action_kind: MutatingKind
    level: AutonomyLevel


class AiSettingsResponse(BaseModel):
    switches: dict[str, Any]
    grants: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Agents / commands
# ---------------------------------------------------------------------------

CaptureSource = Literal["user_command", "email", "meeting", "comment", "document"]


class DraftRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    # Only ever *lowers* privileges: anything but user_command can never auto-execute.
    source: CaptureSource = "user_command"
    project_id: Optional[str] = None


class DraftResponse(BaseModel):
    proposal: ProposalResponse
    duplicate_warning: Optional[ProposalResponse] = None
    draft: dict[str, Any]


class SprintRequest(BaseModel):
    capacity: int = Field(default=5, ge=1, le=25)
    project_id: Optional[str] = None


class ScanRequest(BaseModel):
    project_id: Optional[str] = None


class CommandRequest(BaseModel):
    command: str = Field(min_length=1, max_length=2000)
    project_id: Optional[str] = None


class CommandResponse(BaseModel):
    # read: answered immediately | proposal: mutation queued for approval
    # clarify: ambiguous, nothing done | unsupported: understood but not available
    mode: Literal["read", "proposal", "clarify", "unsupported"]
    answer: str
    data: dict[str, Any] = Field(default_factory=dict)
    proposals: list[ProposalResponse] = Field(default_factory=list)
