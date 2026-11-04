import json
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class CommitmentResponse(BaseModel):
    id: str
    owner_id: str
    description: str
    responsible_party: Optional[str] = None
    counterparty: Optional[str] = None
    direction: str = "owed_by_me"
    due_date: Optional[str] = None
    original_due_date_text: Optional[str] = None
    normalized_due_date: Optional[datetime] = None
    timezone: Optional[str] = "UTC"
    confidence: Optional[float] = 1.0
    evidence: Optional[str] = None
    priority: str = "medium"
    source_type: str
    source_ref: str
    source_metadata: Optional[dict[str, Any]] = None
    status: str
    effective_status: Optional[str] = None
    linked_task_id: Optional[str] = None
    verification_status: str = "unverified"
    verification_evidence: Optional[str] = None
    verification_reasoning: Optional[str] = None
    review_required: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CommitmentCreateRequest(BaseModel):
    description: str
    responsible_party: Optional[str] = None
    counterparty: Optional[str] = None
    direction: str = "owed_by_me"
    due_date: Optional[str] = None
    priority: Optional[str] = "medium"
    evidence: Optional[str] = None
    source_type: Optional[str] = "manual"
    source_ref: Optional[str] = None


class CommitmentUpdateRequest(BaseModel):
    description: Optional[str] = None
    responsible_party: Optional[str] = None
    counterparty: Optional[str] = None
    direction: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    verification_status: Optional[str] = None
    verification_evidence: Optional[str] = None
    verification_reasoning: Optional[str] = None
    linked_task_id: Optional[str] = None


class CommitmentVerificationRequest(BaseModel):
    verification_status: Optional[str] = None  # "verified" | "rejected" | "verification_pending"
    evidence: Optional[str] = None
    reasoning: Optional[str] = None


class CommitmentScanResult(BaseModel):
    scanned_gmail: int
    scanned_meeting_items: int
    created: int
    updated: int
    commitments: list[CommitmentResponse]
    total_messages: Optional[int] = 0
    processed_messages: Optional[int] = 0
    successful_messages: Optional[int] = 0
    no_commitment_messages: Optional[int] = 0
    failed_messages: Optional[int] = 0
    commitments_found: Optional[int] = 0
    status: Optional[str] = "completed"
    warnings: list[str] = []
    errors: list[str] = []


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


# Execution Tracking Schemas (Phase 2)

class CommitmentRunStageResponse(BaseModel):
    id: str
    stage_name: str
    stage_order: int
    status: str
    progress_percent: int
    processed_count: int
    total_count: int
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class CommitmentRunResponse(BaseModel):
    id: str
    run_id: str
    owner_id: str
    run_type: str
    status: str
    current_stage: Optional[str] = None
    progress_percent: int
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    commitments_found: int
    created_count: int
    updated_count: int
    warnings: list[str] = []
    errors: list[str] = []
    result_summary: Optional[dict[str, Any]] = None
    cancel_requested: bool = False
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    stages: list[CommitmentRunStageResponse] = []

    model_config = ConfigDict(from_attributes=True)


class CommitmentRunCreateRequest(BaseModel):
    run_type: str = "scan"  # "scan" | "sweep"
    max_emails: Optional[int] = 10


class CommitmentStatsResponse(BaseModel):
    total: int
    pending: int
    at_risk: int
    overdue: int
    completed: int
    dismissed: int
    completion_rate: float
    newly_discovered_this_week: int
    awaiting_others: int
    owed_by_me: int
    owed_to_me: int
    mutual: int = 0
    unknown: int = 0


class CommitmentEventResponse(BaseModel):
    id: str
    commitment_id: str
    owner_id: str
    event_type: str
    actor_id: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FollowUpDraftResponse(BaseModel):
    commitment_id: str
    counterparty: Optional[str] = None
    suggested_follow_up_date: Optional[str] = None
    reason: str
    subject: str
    body: str


class CommitmentAnalyticsResponse(BaseModel):
    stats: CommitmentStatsResponse
    status_distribution: dict[str, int]
    direction_distribution: dict[str, int]
    source_distribution: dict[str, int]
    priority_distribution: dict[str, int]
    top_counterparties: list[dict[str, Any]]
    actionable_insights: list[dict[str, Any]]
