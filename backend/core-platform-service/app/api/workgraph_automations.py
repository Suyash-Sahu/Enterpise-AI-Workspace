"""
AMOF Work automations API (PRD v3 §7.1), mounted under the existing /workgraph prefix.

    GET  /automations                 list rules
    POST /automations                 create a DRAFT rule from structured JSON or a natural-language sentence
    POST /automations/preview         stateless dry-run of a definition / sentence (nothing is stored)
    GET  /automations/{id}            rule + recent runs
    POST /automations/{id}/preview    dry-run the stored rule; required before activation
    POST /automations/{id}/activate   draft -> active (409 unless the current definition was previewed)
    POST /automations/{id}/pause | resume
    POST /automations/{id}/run        evaluate now (same limits/kill switch as the scheduled tick)

Rules are never editable and never active on creation; the owner comes from the
authenticated user only.
"""
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.services.work_ai import automations, guard

router = APIRouter(prefix="/workgraph", tags=["WorkGraph Automations"])


class RuleInput(BaseModel):
    """Exactly one of `text` (natural language) or `definition` (structured)."""
    text: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    definition: Optional[automations.RuleDefinition] = None
    project_id: Optional[str] = None  # applies to `text`; a definition carries its own

    @model_validator(mode="after")
    def _one(self):
        if (self.text is None) == (self.definition is None):
            raise ValueError("Provide exactly one of 'text' or 'definition'.")
        return self


class AutomationResponse(BaseModel):
    id: str
    project_id: Optional[str] = None
    name: str
    source_text: Optional[str] = None
    trigger: dict[str, Any]
    conditions: dict[str, Any]
    actions: list[dict[str, Any]]
    status: str
    previewed: bool = False
    activated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class RunResponse(BaseModel):
    id: int
    automation_id: str
    status: str
    matched_count: int
    proposals_created: int
    executed_count: int
    detail: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    model_config = ConfigDict(from_attributes=True)


class BuildResponse(BaseModel):
    needs_clarification: bool = False
    clarification: Optional[str] = None
    automation: Optional[AutomationResponse] = None
    definition: Optional[dict[str, Any]] = None
    preview: Optional[dict[str, Any]] = None
    warnings: list[str] = Field(default_factory=list)


def _oid(u: User) -> str:
    return str(u.id)


def _rule_dto(rule) -> AutomationResponse:
    dto = AutomationResponse.model_validate(rule)
    dto.previewed = rule.previewed_hash == rule.definition_hash
    return dto


def _err(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=409, detail=str(exc))
    if isinstance(exc, guard.KillSwitchOff):
        return HTTPException(status_code=423, detail=str(exc))
    return HTTPException(status_code=400, detail=str(exc))


_MAPPED = (ValueError, LookupError, PermissionError, guard.KillSwitchOff)


def _definition(db: Session, user: User, body: RuleInput):
    """-> (definition | None, draft-or-None, source_text). Natural language is parsed deterministically."""
    if body.definition is not None:
        return body.definition, None, None
    draft = automations.parse_rule_text(db, _oid(user), body.text or "", user_email=user.email, project_id=body.project_id)
    return draft.definition, draft, body.text


@router.get("/automations", response_model=list[AutomationResponse])
def list_automations(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return [_rule_dto(r) for r in automations.list_rules(db, _oid(current_user))]


@router.post("/automations", response_model=BuildResponse, status_code=201)
def create_automation(body: RuleInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        defn, draft, source = _definition(db, current_user, body)
        if defn is None:
            return BuildResponse(needs_clarification=True, clarification=draft.clarification)
        rule = automations.create_rule(db, _oid(current_user), defn, source_text=source)
    except _MAPPED as exc:
        raise _err(exc) from exc
    return BuildResponse(automation=_rule_dto(rule), definition=defn.model_dump(mode="json"),
                         warnings=draft.warnings if draft else ["Not active yet: preview it, then activate it."])


@router.post("/automations/preview", response_model=BuildResponse)
def preview_definition(body: RuleInput, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Stateless dry-run (nothing stored). Activation still requires previewing the *stored* rule."""
    try:
        defn, draft, _ = _definition(db, current_user, body)
        if defn is None:
            return BuildResponse(needs_clarification=True, clarification=draft.clarification)
        result = automations.dry_run(db, _oid(current_user), defn.project_id, defn.trigger.model_dump(mode="json"),
                                     defn.conditions.model_dump(mode="json"), [a.model_dump(mode="json") for a in defn.actions])
    except _MAPPED as exc:
        raise _err(exc) from exc
    return BuildResponse(definition=defn.model_dump(mode="json"), preview=result,
                         warnings=draft.warnings if draft else [])


@router.get("/automations/{automation_id}")
def get_automation(automation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    rule = automations.get_rule(db, _oid(current_user), automation_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Automation not found.")
    return {"automation": _rule_dto(rule),
            "runs": [RunResponse.model_validate(r) for r in automations.list_runs(db, _oid(current_user), automation_id, 20)]}


@router.get("/automations/{automation_id}/runs", response_model=list[RunResponse])
def automation_runs(automation_id: str, limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db),
                    current_user: User = Depends(get_current_user)):
    try:
        return automations.list_runs(db, _oid(current_user), automation_id, limit)
    except _MAPPED as exc:
        raise _err(exc) from exc


@router.post("/automations/{automation_id}/preview")
def preview_automation(automation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return automations.preview_rule(db, _oid(current_user), automation_id)
    except _MAPPED as exc:
        raise _err(exc) from exc


@router.post("/automations/{automation_id}/activate", response_model=AutomationResponse)
def activate_automation(automation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return _rule_dto(automations.activate(db, _oid(current_user), automation_id))
    except _MAPPED as exc:
        raise _err(exc) from exc


@router.post("/automations/{automation_id}/pause", response_model=AutomationResponse)
def pause_automation(automation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return _rule_dto(automations.pause(db, _oid(current_user), automation_id))
    except _MAPPED as exc:
        raise _err(exc) from exc


@router.post("/automations/{automation_id}/resume", response_model=AutomationResponse)
def resume_automation(automation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return _rule_dto(automations.activate(db, _oid(current_user), automation_id, resume=True))
    except _MAPPED as exc:
        raise _err(exc) from exc


@router.post("/automations/{automation_id}/run", response_model=Optional[RunResponse])
def run_automation(automation_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Evaluate now. Null when nothing matched. Subject to the kill switch, blast radius and rate limit."""
    try:
        return automations.run_now(db, _oid(current_user), automation_id)
    except _MAPPED as exc:
        raise _err(exc) from exc
