"""
Commitment Intelligence Center API Router.
Full-stack implementation for Phase 1-6:
- Persistent background runs and stage monitoring (/runs)
- Discovery, verification, and smart follow-ups
- Lifecycle management (CRUD, complete, dismiss, reopen)
- Real database-backed statistics and analytics
- Backward-compatible scan/sweep endpoints
"""
import json
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.workgraph_ai import _MAPPED, http_error
from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.execution import ExecutionRequest
from app.schemas.commitment import (
    CommitmentResponse,
    CommitmentScanResult,
    CommitmentSweepResult,
    CommitmentRunResponse,
    CommitmentRunCreateRequest,
    CommitmentRunStageResponse,
    CommitmentStatsResponse,
    CommitmentCreateRequest,
    CommitmentUpdateRequest,
    CommitmentVerificationRequest,
    CommitmentEventResponse,
    FollowUpDraftResponse,
    CommitmentAnalyticsResponse,
)
from app.services.commitment_service import commitment_service
from app.services.commitment_run_service import commitment_run_service
from app.services.execution_manager import execution_manager
from app.services.work_ai import orchestrator

router = APIRouter(prefix="/commitments", tags=["Commitments"])


def _serialize_run(run) -> CommitmentRunResponse:
    stages = [
        CommitmentRunStageResponse.model_validate(stg)
        for stg in (run.stages or [])
    ]
    warnings = json.loads(run.warnings) if run.warnings else []
    errors = json.loads(run.errors) if run.errors else []
    summary = json.loads(run.result_summary) if run.result_summary else {}

    return CommitmentRunResponse(
        id=run.id,
        run_id=run.id,
        owner_id=run.owner_id,
        run_type=run.run_type,
        status=run.status,
        current_stage=run.current_stage,
        progress_percent=run.progress_percent,
        total_items=run.total_items,
        processed_items=run.processed_items,
        successful_items=run.successful_items,
        failed_items=run.failed_items,
        commitments_found=run.commitments_found,
        created_count=run.created_count,
        updated_count=run.updated_count,
        warnings=warnings,
        errors=errors,
        result_summary=summary,
        cancel_requested=run.cancel_requested,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        stages=stages,
    )


# ---------------------------------------------------------------------------
# Persistent Execution Runs (Phase 2)
# ---------------------------------------------------------------------------

@router.post("/runs", response_model=CommitmentRunResponse)
def start_run(
    req: CommitmentRunCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owner_id = str(current_user.id)
    user_tz = getattr(current_user, "timezone", "UTC") or "UTC"
    run = commitment_run_service.create_run(db, owner_id=owner_id, run_type=req.run_type)

    if run.status == "queued" and run.progress_percent == 0 and not run.started_at:
        if req.run_type == "scan":
            commitment_run_service.start_background_scan(
                run_id=run.id,
                owner_id=owner_id,
                max_emails=req.max_emails or 10,
                user_tz=user_tz,
            )
        elif req.run_type == "sweep":
            commitment_run_service.start_background_sweep(
                run_id=run.id,
                owner_id=owner_id,
                max_emails=req.max_emails or 10,
                user_email=current_user.email,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported run type '{req.run_type}'")

    return _serialize_run(run)


@router.get("/runs/active", response_model=Optional[CommitmentRunResponse])
def get_active_run(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = commitment_run_service.get_latest_active_run(db, str(current_user.id))
    if not run:
        return None
    return _serialize_run(run)


@router.get("/runs/{run_id}", response_model=CommitmentRunResponse)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = commitment_run_service.get_run(db, run_id=run_id, owner_id=str(current_user.id))
    if not run:
        raise HTTPException(status_code=404, detail="Execution run not found")
    return _serialize_run(run)


@router.post("/runs/{run_id}/cancel", response_model=CommitmentRunResponse)
def cancel_run(
    run_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run = commitment_run_service.cancel_run(db, run_id=run_id, owner_id=str(current_user.id))
    if not run:
        raise HTTPException(status_code=404, detail="Execution run not found or already finished")
    return _serialize_run(run)


@router.get("/runs", response_model=list[CommitmentRunResponse])
def list_runs(
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    runs = commitment_run_service.list_runs(db, owner_id=str(current_user.id), limit=limit)
    return [_serialize_run(r) for r in runs]


# ---------------------------------------------------------------------------
# Statistics & Analytics (Phase 6)
# ---------------------------------------------------------------------------

@router.get("/stats", response_model=CommitmentStatsResponse)
def get_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = commitment_service.get_stats(db, str(current_user.id))
    return CommitmentStatsResponse(**stats)


@router.get("/analytics", response_model=CommitmentAnalyticsResponse)
def get_analytics(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analytics = commitment_service.get_analytics(db, str(current_user.id))
    return CommitmentAnalyticsResponse(**analytics)


# ---------------------------------------------------------------------------
# Commitment Workspace CRUD & Lifecycle (Phase 4)
# ---------------------------------------------------------------------------

@router.get("", response_model=list[CommitmentResponse])
def list_commitments(
    status_filter: Optional[str] = Query(None, alias="status_filter"),
    direction: Optional[str] = None,
    source_type: Optional[str] = None,
    priority: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    commitments = commitment_service.list_commitments(
        db=db,
        owner_id=str(current_user.id),
        status=status_filter,
        direction=direction,
        source_type=source_type,
        priority=priority,
        search=search,
        limit=limit,
        offset=offset,
    )
    return [CommitmentResponse.model_validate(c) for c in commitments]


@router.post("", response_model=CommitmentResponse, status_code=status.HTTP_201_CREATED)
def create_commitment(
    req: CommitmentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_tz = getattr(current_user, "timezone", "UTC") or "UTC"
    row = commitment_service.create_commitment(
        db=db,
        owner_id=str(current_user.id),
        description=req.description,
        responsible_party=req.responsible_party,
        counterparty=req.counterparty,
        direction=req.direction,
        due_date=req.due_date,
        priority=req.priority or "medium",
        evidence=req.evidence,
        source_type=req.source_type or "manual",
        source_ref=req.source_ref,
        user_tz=user_tz,
    )
    return CommitmentResponse.model_validate(row)


@router.get("/{commitment_id}", response_model=CommitmentResponse)
def get_commitment(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = commitment_service.get_commitment(db, commitment_id=commitment_id, owner_id=str(current_user.id))
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return CommitmentResponse.model_validate(c)


@router.patch("/{commitment_id}", response_model=CommitmentResponse)
def update_commitment(
    commitment_id: str,
    req: CommitmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user_tz = getattr(current_user, "timezone", "UTC") or "UTC"
    updates = req.model_dump(exclude_unset=True)
    c = commitment_service.update_commitment(
        db, commitment_id=commitment_id, owner_id=str(current_user.id), updates=updates, user_tz=user_tz
    )
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return CommitmentResponse.model_validate(c)


@router.post("/{commitment_id}/complete", response_model=CommitmentResponse)
def complete_commitment(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = commitment_service.complete_commitment(db, commitment_id=commitment_id, owner_id=str(current_user.id))
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return CommitmentResponse.model_validate(c)


@router.post("/{commitment_id}/dismiss", response_model=CommitmentResponse)
def dismiss_commitment(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = commitment_service.dismiss_commitment(db, commitment_id=commitment_id, owner_id=str(current_user.id))
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return CommitmentResponse.model_validate(c)


@router.post("/{commitment_id}/reopen", response_model=CommitmentResponse)
def reopen_commitment(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = commitment_service.reopen_commitment(db, commitment_id=commitment_id, owner_id=str(current_user.id))
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return CommitmentResponse.model_validate(c)


# ---------------------------------------------------------------------------
# Advanced Intelligence: Verification, Follow-Up, Propose Task (Phase 5)
# ---------------------------------------------------------------------------

@router.post("/{commitment_id}/verify", response_model=CommitmentResponse)
def verify_commitment(
    commitment_id: str,
    req: CommitmentVerificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    c = commitment_service.verify_commitment(
        db=db,
        commitment_id=commitment_id,
        owner_id=str(current_user.id),
        verification_status=req.verification_status,
        evidence=req.evidence,
        reasoning=req.reasoning,
    )
    if not c:
        raise HTTPException(status_code=404, detail="Commitment not found")
    return CommitmentResponse.model_validate(c)


@router.post("/{commitment_id}/follow-up", response_model=FollowUpDraftResponse)
def generate_follow_up(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return commitment_service.generate_follow_up(db, commitment_id=commitment_id, owner_id=str(current_user.id))
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{commitment_id}/propose-task")
def propose_task(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return commitment_service.propose_task(
            db,
            commitment_id=commitment_id,
            owner_id=str(current_user.id),
            user_email=current_user.email,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{commitment_id}/events", response_model=list[CommitmentEventResponse])
def get_commitment_events(
    commitment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.models.commitment_event import CommitmentEvent
    events = (
        db.query(CommitmentEvent)
        .filter(CommitmentEvent.commitment_id == commitment_id, CommitmentEvent.owner_id == str(current_user.id))
        .order_by(CommitmentEvent.created_at.desc())
        .all()
    )
    res = []
    for ev in events:
        details_obj = json.loads(ev.details) if ev.details else {}
        res.append(
            CommitmentEventResponse(
                id=ev.id,
                commitment_id=ev.commitment_id,
                owner_id=ev.owner_id,
                event_type=ev.event_type,
                actor_id=ev.actor_id,
                details=details_obj,
                created_at=ev.created_at,
            )
        )
    return res


# ---------------------------------------------------------------------------
# Backward-Compatible Endpoints
# ---------------------------------------------------------------------------

@router.post("/scan", response_model=CommitmentScanResult)
def scan_commitments(
    max_emails: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owner_id = str(current_user.id)

    res = execution_manager.execute(
        db=db,
        request=ExecutionRequest(
            task_type="commitment.scan",
            input={"max_emails": max_emails},
        ),
        owner_id=owner_id,
    )

    if res.status.value != "COMPLETED" or not res.result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=res.error_message or "Commitment scan failed",
        )

    commitments = commitment_service.list_commitments(db=db, owner_id=owner_id)
    return CommitmentScanResult(
        **res.result,
        commitments=[CommitmentResponse.model_validate(c) for c in commitments],
    )


@router.post("/sweep", response_model=CommitmentSweepResult)
def sweep_commitments(
    max_emails: int = 10,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return orchestrator.commitment_sweep(
            db, str(current_user.id), max_emails=max_emails, user_email=current_user.email
        )
    except _MAPPED as exc:
        raise http_error(exc)
