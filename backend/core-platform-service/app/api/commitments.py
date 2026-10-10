"""
Commitment Tracker API Router.

The scan is dispatched through the real execution path (execution_manager ->
TaskRegistry's "commitment.scan"), same as meeting extraction and the digest,
so it goes through the same audit trail every other capability does. Listing
is a direct owner-scoped read, same as GET /workgraph/tasks.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.workgraph_ai import _MAPPED, http_error
from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.execution import ExecutionRequest
from app.schemas.commitment import CommitmentResponse, CommitmentScanResult, CommitmentSweepResult
from app.services.commitment_service import commitment_service
from app.services.execution_manager import execution_manager
from app.services.work_ai import orchestrator

router = APIRouter(prefix="/commitments", tags=["Commitments"])


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
    """
    Rescan the inbox, draft a task proposal for each unresolved commitment
    (duplicate-checked), then re-scan risk -- one visible autonomous loop over
    agents that already exist (see app/services/work_ai/orchestrator.py).
    Every mutation this produces still lands in the AI Inbox for approval.
    """
    try:
        return orchestrator.commitment_sweep(db, str(current_user.id), max_emails=max_emails, user_email=current_user.email)
    except _MAPPED as exc:
        raise http_error(exc)


@router.get("", response_model=list[CommitmentResponse])
def list_commitments(
    status_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    commitments = commitment_service.list_commitments(
        db=db, owner_id=str(current_user.id), status=status_filter,
    )
    return [CommitmentResponse.model_validate(c) for c in commitments]
