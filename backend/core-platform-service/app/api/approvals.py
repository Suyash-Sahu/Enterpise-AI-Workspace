"""
Project 8 — Approval API Router
Exposes REST endpoints for HITL Approval Lifecycle Management on Port 8001.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.core.config import settings
from app.schemas.approval import (
    ApprovalCreate,
    ApprovalEdit,
    ApprovalReject,
    ApprovalResponse,
    ApprovalPendingListResponse,
    ApprovalEventResponse,
    ApprovalHealthResponse,
)
from app.schemas.execution import ExecutionRequest, ExecutionResponse
from app.services.approval.approval_service import approval_service
from app.services.execution_manager import execution_manager

router = APIRouter(prefix="/approvals", tags=["Project 8 — Approval System"])


@router.get("/health", response_model=ApprovalHealthResponse)
def get_approval_health():
    """
    Returns P8 Approval System health status and configurations.
    """
    return ApprovalHealthResponse(
        status="online",
        approvals_enabled=settings.APPROVALS_ENABLED,
        default_ttl_minutes=settings.APPROVAL_DEFAULT_TTL_MINUTES,
        max_ttl_minutes=settings.APPROVAL_MAX_TTL_MINUTES,
        auto_expire_enabled=settings.APPROVAL_AUTO_EXPIRE_ENABLED,
    )


@router.post("", response_model=ApprovalResponse, status_code=status.HTTP_201_CREATED)
def create_approval(
    data: ApprovalCreate,
    ttl_minutes: Optional[int] = Query(default=None, ge=1, le=1440),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new pending approval record (Internal/Agent/P7 creation).
    """
    workspace_id = f"ws_user_{current_user.id}"
    approval = approval_service.create_approval(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        data=data,
        ttl_minutes=ttl_minutes,
    )
    return approval_service.to_response_dto(approval)


@router.get("/pending", response_model=ApprovalPendingListResponse)
def list_pending_approvals(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns a list of pending non-expired approvals for the authenticated user and workspace.
    """
    workspace_id = f"ws_user_{current_user.id}"
    items, total = approval_service.list_pending(
        db=db,
        user_id=current_user.id,
        workspace_id=workspace_id,
        skip=skip,
        limit=limit,
    )
    dtos = [approval_service.to_response_dto(item) for item in items]
    return ApprovalPendingListResponse(items=dtos, total=total)


@router.get("/{approval_id}", response_model=ApprovalResponse)
def get_approval_details(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed approval record by ID. Tenant-isolated to current authenticated user.
    """
    workspace_id = f"ws_user_{current_user.id}"
    approval = approval_service.get_approval(
        db=db,
        approval_id=approval_id,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )
    return approval_service.to_response_dto(approval)


@router.get("/{approval_id}/events", response_model=list[ApprovalEventResponse])
def get_approval_audit_timeline(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve full audit log timeline for an approval record.
    """
    workspace_id = f"ws_user_{current_user.id}"
    events = approval_service.get_approval_events(
        db=db,
        approval_id=approval_id,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )
    return [
        ApprovalEventResponse(
            id=e.id,
            approval_id=e.approval_id,
            user_id=e.user_id,
            event_type=e.event_type,
            old_status=e.old_status,
            new_status=e.new_status,
            metadata_json=e.metadata_json,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
def approve_action(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Approve action record (PENDING -> APPROVED).
    """
    workspace_id = f"ws_user_{current_user.id}"
    approval = approval_service.approve(
        db=db,
        approval_id=approval_id,
        user_id=current_user.id,
        workspace_id=workspace_id,
    )
    return approval_service.to_response_dto(approval)


@router.post("/{approval_id}/execute", response_model=ExecutionResponse)
def execute_approved_action(
    approval_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Dispatches an approved action through the real capability registry.

    AMOF-X Phase 5: this is the only path from "approved" to "actually
    happened" for a capability with no dedicated hand-built endpoint of its
    own (like app/api/connectors.py's gmail/send, which predates this and
    remains the endpoint the manual-compose UI flow uses). Before this
    existed, approving a Supervisor-originated approval (Project 7 pausing a
    plan on `gmail.send`) changed a status flag and nothing else -- there was
    no code path that ever called the real handler, approved or not. This
    generalizes the existing claim invariant to any registered capability,
    not just Gmail, via ExecutionRequest.approval_id -- the actual atomic
    claim (APPROVED -> EXECUTING) happens in
    app/execution/executor.py::execute_task, not here; this is a thin
    dispatch, not a second enforcement point.
    """
    workspace_id = f"ws_user_{current_user.id}"
    approval = approval_service.get_approval(
        db=db, approval_id=approval_id, user_id=current_user.id, workspace_id=workspace_id,
    )

    exec_request = ExecutionRequest(
        task_type=approval.action_type,
        # Discarded by the executor once the claim succeeds -- it resolves
        # and uses the approval's own (possibly edited) payload instead, not
        # this value. Present only because ExecutionRequest.input is
        # required.
        input=approval.payload or {},
        approval_id=approval.id,
        metadata={"workspace_id": workspace_id},
    )
    return execution_manager.execute(db=db, request=exec_request, owner_id=str(current_user.id))


@router.post("/{approval_id}/edit", response_model=ApprovalResponse)
def edit_approval_payload(
    approval_id: int,
    data: ApprovalEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Edit payload parameters. Status remains PENDING for explicit user review and approval.
    """
    workspace_id = f"ws_user_{current_user.id}"
    approval = approval_service.edit(
        db=db,
        approval_id=approval_id,
        user_id=current_user.id,
        workspace_id=workspace_id,
        data=data,
    )
    return approval_service.to_response_dto(approval)


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
def reject_action(
    approval_id: int,
    data: Optional[ApprovalReject] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Reject action record (PENDING -> REJECTED).
    """
    workspace_id = f"ws_user_{current_user.id}"
    approval = approval_service.reject(
        db=db,
        approval_id=approval_id,
        user_id=current_user.id,
        workspace_id=workspace_id,
        data=data,
    )
    return approval_service.to_response_dto(approval)
