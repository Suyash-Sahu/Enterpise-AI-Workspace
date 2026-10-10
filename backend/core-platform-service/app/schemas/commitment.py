from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class CommitmentResponse(BaseModel):
    id: str
    owner_id: str
    description: str
    responsible_party: Optional[str] = None
    due_date: Optional[str] = None
    source_type: str
    source_ref: str
    status: str
    linked_task_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommitmentScanResult(BaseModel):
    scanned_gmail: int
    scanned_meeting_items: int
    created: int
    updated: int
    commitments: list[CommitmentResponse]


class SweepScanSummary(BaseModel):
    scanned_gmail: int
    scanned_meeting_items: int
    created: int
    updated: int


class SweepStep(BaseModel):
    step: str
    label: str
    detail: str
    count: int = 0


class CommitmentSweepResult(BaseModel):
    steps: list[SweepStep]
    scan: SweepScanSummary
    proposals_created: int
    duplicate_warnings: int
    risk_alerts_created: int
    skipped_already_proposed: int
