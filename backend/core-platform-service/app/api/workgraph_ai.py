"""
AMOF Work AI layer API (PRD v3 §6). Mounted under the existing /workgraph prefix.

Every route derives the tenant from the authenticated user; no owner/project
identifier from the client is trusted (project ids are re-verified server-side).
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.work_ai import (
    AiSettingsResponse,
    AutonomyRequest,
    CommandRequest,
    CommandResponse,
    DraftRequest,
    DraftResponse,
    KillSwitchRequest,
    ProposalDecision,
    ProposalResponse,
    ScanRequest,
    SprintRequest,
)
from app.services.work_ai import command as work_command, guard, orchestrator, pipeline

router = APIRouter(prefix="/workgraph", tags=["WorkGraph AI"])

_MAPPED = (ValueError, LookupError, PermissionError, guard.KillSwitchOff, guard.AutonomyViolation)


def _oid(user: User) -> str:
    return str(user.id)


def http_error(exc: Exception) -> HTTPException:
    """One place that maps guard/pipeline errors to HTTP semantics (shared by AI routes)."""
    if isinstance(exc, guard.KillSwitchOff):
        return HTTPException(status_code=423, detail=str(exc))
    if isinstance(exc, (guard.AutonomyViolation, PermissionError)):
        return HTTPException(status_code=403, detail=str(exc))
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


# ------------------------------------------------------------------ AI Inbox

@router.get("/inbox", response_model=list[ProposalResponse])
def inbox(
    status: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    project_id: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return pipeline.list_proposals(db, _oid(current_user), status=status, kind=kind, project_id=project_id, limit=limit)


@router.get("/inbox/{proposal_id}", response_model=ProposalResponse)
def inbox_item(proposal_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    prop = pipeline.get_proposal(db, _oid(current_user), proposal_id)
    if prop is None:
        raise HTTPException(status_code=404, detail="Proposal not found")
    return prop


@router.post("/inbox/{proposal_id}/approve", response_model=ProposalResponse)
def approve_proposal(
    proposal_id: str,
    body: ProposalDecision = ProposalDecision(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return pipeline.decide(db, _oid(current_user), proposal_id, True, edited_payload=body.edited_payload)
    except _MAPPED as exc:
        raise http_error(exc) from exc


@router.post("/inbox/{proposal_id}/reject", response_model=ProposalResponse)
def reject_proposal(
    proposal_id: str,
    body: ProposalDecision = ProposalDecision(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return pipeline.decide(db, _oid(current_user), proposal_id, False, reason=body.reason)
    except _MAPPED as exc:
        raise http_error(exc) from exc


# ------------------------------------------------------------------ kill switch + autonomy

@router.get("/ai/settings", response_model=AiSettingsResponse)
def ai_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    oid = _oid(current_user)
    return AiSettingsResponse(
        switches=guard.get_switches(db, oid),
        grants=[
            {"project_id": g.project_id, "action_kind": g.action_kind, "level": g.level}
            for g in guard.list_grants(db, oid)
        ],
    )


@router.put("/ai/kill-switch")
def kill_switch(body: KillSwitchRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return guard.set_enabled(db, _oid(current_user), body.enabled, body.project_id)
    except _MAPPED as exc:
        raise http_error(exc) from exc


@router.put("/ai/autonomy")
def set_autonomy(body: AutonomyRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return guard.set_grant(db, _oid(current_user), body.project_id, body.action_kind, body.level)
    except _MAPPED as exc:
        raise http_error(exc) from exc


# ------------------------------------------------------------------ agents (Smart Capture, Focus, Risk, Sprint)

@router.post("/ai/draft", response_model=DraftResponse)
def ai_draft(body: DraftRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Smart Capture: never creates the item -- returns a proposal for approval."""
    try:
        out = orchestrator.capture(
            db, _oid(current_user), body.text, source=body.source, project_id=body.project_id,
            user_email=current_user.email,
        )
    except _MAPPED as exc:
        raise http_error(exc) from exc
    return DraftResponse(
        proposal=ProposalResponse.model_validate(out["proposal"]),
        duplicate_warning=ProposalResponse.model_validate(out["duplicate_warning"]) if out["duplicate_warning"] else None,
        draft=out["draft"].model_dump(),
    )


@router.get("/ai/focus-plan")
def ai_focus_plan(
    project_id: Optional[str] = Query(default=None),
    limit: int = Query(default=7, ge=1, le=25),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return orchestrator.focus_plan(db, _oid(current_user), project_id=project_id, limit=limit,
                                       user_email=current_user.email).model_dump()
    except _MAPPED as exc:
        raise http_error(exc) from exc


@router.get("/ai/risks")
def ai_risks(
    project_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return orchestrator.risks(db, _oid(current_user), project_id=project_id).model_dump()
    except _MAPPED as exc:
        raise http_error(exc) from exc


@router.post("/ai/risks/scan", response_model=list[ProposalResponse])
def ai_risks_scan(body: ScanRequest = ScanRequest(), db: Session = Depends(get_db),
                  current_user: User = Depends(get_current_user)):
    """Publishes current risks to the AI Inbox as informational alerts."""
    try:
        return orchestrator.scan_risks(db, _oid(current_user), project_id=body.project_id)
    except _MAPPED as exc:
        raise http_error(exc) from exc


@router.post("/ai/sprint-plan", response_model=ProposalResponse)
def ai_sprint_plan(body: SprintRequest = SprintRequest(), db: Session = Depends(get_db),
                   current_user: User = Depends(get_current_user)):
    try:
        return orchestrator.sprint_plan(db, _oid(current_user), capacity=body.capacity, project_id=body.project_id)
    except _MAPPED as exc:
        raise http_error(exc) from exc


# ------------------------------------------------------------------ AI Work Command

@router.post("/ai/execute", response_model=CommandResponse)
def ai_execute(body: CommandRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """
    Natural-language command. Read-only commands are answered immediately; every
    mutating command returns a proposal (mode="proposal") instead of acting.
    """
    try:
        out = work_command.execute(db, _oid(current_user), body.command, project_id=body.project_id,
                                   user_email=current_user.email)
    except _MAPPED as exc:
        raise http_error(exc) from exc
    return CommandResponse(
        mode=out["mode"], answer=out["answer"], data=out["data"],
        proposals=[ProposalResponse.model_validate(p) for p in out["proposals"]],
    )
