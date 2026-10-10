"""
AMOF Work AI proposal pipeline (PRD v3 §6.1/§10).

    Authorization -> Privacy classification -> Proposal -> Approval/Autonomy
    policy -> Execution -> Verification -> Audit

ONE authorization path: a mutating proposal owns a real `Approval` row
(app/services/approval) and executes only through execution_manager, whose
executor atomically claims that Approval (APPROVED -> EXECUTING, replay-safe)
before the capability handler (app/execution/work_handlers.py) runs. L3 is not
a bypass: the autonomy policy approves the *same* Approval on the user's
behalf (audited as AUTO_APPROVED_L3) and the executor still claims it.

Agents never call this module's execution half; they return typed output and
the orchestrator turns it into a proposal via create_proposal().
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.approval import Approval
from app.models.work_ai import AiProposal
from app.privacy.classifier import privacy_classifier
from app.schemas.approval import ApprovalCreate, ApprovalEdit, ApprovalReject
from app.schemas.execution import ExecutionRequest
from app.schemas.workgraph import DependencyCreate, TaskCreate, TaskUpdate
from app.services.approval.approval_audit import approval_audit
from app.services.approval.approval_service import approval_service
from app.services.execution_manager import execution_manager
from app.services.work_ai import guard
from app.services.workgraph_service import workgraph_service

logger = logging.getLogger(__name__)

_MAX_PAYLOAD_CHARS = 20_000
# What a reviewer may change in the approval UI. Scope/provenance fields
# (task_id, project_id, proposal_id, link ids) are never editable.
_EDITABLE = {
    "create_item": {"title", "description", "priority", "assignee", "due_date", "type"},
    "update_item": {"title", "description", "priority", "assignee", "due_date", "type", "status"},
    "link_items": set(),
}


def _ws(owner_id: str) -> str:
    return f"ws_user_{owner_id}"


# ------------------------------------------------------------------ validation

def _owned_task(db: Session, owner_id: str, task_id: Any):
    task = workgraph_service.get_task(db, owner_id, str(task_id)) if task_id else None
    if task is None:
        raise ValueError("Referenced work item not found.")
    return task


def normalize_payload(db: Session, owner_id: str, kind: str, payload: dict) -> tuple[dict, Optional[str]]:
    """
    Validate + whitelist `payload` and derive the project scope server-side.
    Every id in it is re-checked against owner_id here (and again by the
    service at execution time). Returns (clean_payload, project_id).
    """
    if kind not in guard.ALL_KINDS:
        raise ValueError(f"Unknown proposal kind '{kind}'.")
    if not isinstance(payload, dict) or len(json.dumps(payload, default=str)) > _MAX_PAYLOAD_CHARS:
        raise ValueError("Invalid or oversized proposal payload.")

    if kind == "create_item":
        clean = TaskCreate(**payload).model_dump(mode="json", exclude_none=True)
        project_id = clean.get("project_id")
        if project_id and workgraph_service.get_project(db, owner_id, project_id) is None:
            raise ValueError("Project not found.")
        for dep in clean.get("depends_on", []):
            _owned_task(db, owner_id, dep)
        return clean, project_id

    if kind == "update_item":
        task = _owned_task(db, owner_id, payload.get("task_id"))
        fields = TaskUpdate(**{k: v for k, v in payload.items() if k != "task_id"}).model_dump(
            mode="json", exclude_unset=True, exclude_none=True
        )
        if not fields:
            raise ValueError("update_item needs at least one field to change.")
        return {"task_id": task.id, **fields}, task.project_id

    if kind == "link_items":
        a = _owned_task(db, owner_id, payload.get("task_id"))
        b = _owned_task(db, owner_id, payload.get("other_task_id"))
        link = DependencyCreate(depends_on_task_id=b.id, kind=payload.get("link_kind", "BLOCKED_BY"))
        if a.id == b.id:
            raise ValueError("A task cannot be linked to itself.")
        return {"task_id": a.id, "other_task_id": b.id, "link_kind": link.kind}, a.project_id

    # informational kinds: opaque JSON for display; only the project scope is verified
    project_id = payload.get("project_id")
    if project_id and workgraph_service.get_project(db, owner_id, project_id) is None:
        raise ValueError("Project not found.")
    return payload, project_id


def _classify(payload: dict) -> str:
    """Privacy classification of the proposal content. Fails closed to 'confidential'."""
    text = " ".join(str(payload.get(k, "")) for k in ("title", "description", "text", "summary"))
    try:
        return privacy_classifier.classify(text).label.value
    except Exception:
        logger.exception("[WorkAI] privacy classification failed; treating as confidential")
        return "confidential"


# ------------------------------------------------------------------ creation

def create_proposal(
    db: Session,
    owner_id: str,
    *,
    kind: str,
    payload: dict,
    agent: str,
    source: str,
    source_ref: Optional[str] = None,
    confidence: Optional[float] = None,
    explanation: str = "",
    allow_auto: bool = True,
) -> AiProposal:
    """
    The ONLY way agent output becomes actionable. Never executes anything
    unless the user holds an explicit L3 grant for this (project, kind).
    """
    clean, project_id = normalize_payload(db, owner_id, kind, payload)
    guard.assert_enabled(db, owner_id, project_id)  # KillSwitchOff -> no proposal at all

    mutating = kind in guard.MUTATING_KINDS
    level = guard.effective_level(db, owner_id, project_id, kind) if mutating else guard.DEFAULT_LEVEL
    if mutating and level == "L0":
        raise guard.AutonomyViolation("Autonomy level L0 (observe-only) forbids proposing mutations here.")

    prop = AiProposal(
        owner_id=owner_id,
        project_id=project_id,
        kind=kind,
        agent=agent,
        payload=clean,
        source=source,
        source_ref=source_ref,
        status="PENDING",
        confidence=None if confidence is None else max(0.0, min(1.0, float(confidence))),
        explanation=(explanation or "")[:2000],
        privacy_tier=_classify(clean),
        autonomy_level=level,
    )
    db.add(prop)
    db.flush()  # need prop.id for the approval payload

    if mutating:
        approval = approval_service.create_approval(
            db=db,
            user_id=int(owner_id),
            workspace_id=_ws(owner_id),
            data=ApprovalCreate(
                action_type=guard.MUTATING_KINDS[kind],
                title=f"AI proposal ({agent}): {kind}",
                description=prop.explanation or None,
                payload={**clean, "proposal_id": prop.id},
                risk_level="medium",
            ),
        )
        prop.approval_id = approval.id
    db.commit()
    db.refresh(prop)

    if mutating and level == "L3" and allow_auto:
        try:
            return _approve_and_run(db, prop, decided_by=f"autonomy:L3:{project_id}:{kind}", auto=True)
        except (guard.AutonomyViolation, guard.KillSwitchOff) as exc:
            # Bad/ineligible grant or switch flipped: stay PENDING for a human.
            logger.warning("[WorkAI] L3 auto-run refused for %s: %s", prop.id, exc)
            guard._audit(db, owner_id, f"work.l3.refused:{project_id}:{kind}")
            db.refresh(prop)
    return prop


# ------------------------------------------------------------------ decision

def _get_owned(db: Session, owner_id: str, proposal_id: str) -> Optional[AiProposal]:
    return db.query(AiProposal).filter(AiProposal.id == proposal_id, AiProposal.owner_id == owner_id).first()


def _approve_and_run(
    db: Session,
    prop: AiProposal,
    *,
    decided_by: str,
    auto: bool = False,
    edited_payload: Optional[dict] = None,
) -> AiProposal:
    owner_id = prop.owner_id
    if auto and not guard.l3_eligible(prop.kind):
        # Execution-layer hard stop: holds even if a bad L3 grant row exists.
        raise guard.AutonomyViolation(f"'{prop.kind}' is not eligible for L3 auto-execution.")
    guard.assert_enabled(db, owner_id, prop.project_id)
    if prop.status != "PENDING":
        raise ValueError(f"Proposal is already {prop.status}.")

    uid, ws = int(owner_id), _ws(owner_id)
    try:
        approval = approval_service.get_approval(db, prop.approval_id, uid, ws)  # also expires stale ones
        if approval.status == "expired":
            prop.status = "EXPIRED"
            db.commit()
            raise ValueError("Proposal expired.")
        if edited_payload:
            allowed = _EDITABLE.get(prop.kind, set())
            changes = {k: v for k, v in edited_payload.items() if k in allowed}
            merged, _ = normalize_payload(db, owner_id, prop.kind, {**prop.payload, **changes})
            approval_service.edit(db, prop.approval_id, uid, ws, ApprovalEdit(edited_payload={**merged, "proposal_id": prop.id}))
        approval_service.approve(db, prop.approval_id, uid, ws)
    except HTTPException as exc:
        raise ValueError(str(exc.detail)) from exc

    if auto:
        approval_audit.log_event(
            db=db, approval_id=prop.approval_id, user_id=uid, event_type="AUTO_APPROVED_L3",
            old_status="pending", new_status="approved", metadata_json={"decided_by": decided_by, "proposal_id": prop.id},
        )
    prop.status = "APPROVED"
    prop.decided_by = decided_by
    prop.decided_at = datetime.now(timezone.utc)
    db.commit()

    resp = execution_manager.execute(
        db=db,
        request=ExecutionRequest(
            task_type=guard.MUTATING_KINDS[prop.kind],
            input={**prop.payload, "proposal_id": prop.id},
            idempotency_key=f"proposal:{prop.id}",
            approval_id=prop.approval_id,
            metadata={"approval_id": prop.approval_id, "proposal_id": prop.id},
        ),
        owner_id=owner_id,
    )
    db.refresh(prop)
    if prop.status != "EXECUTED":  # the handler marks EXECUTED after verifying its own effect
        prop.status = "FAILED"
        prop.error = (resp.error_message or "Execution did not complete.")[:1000]
        db.commit()
    return prop


def decide(
    db: Session,
    owner_id: str,
    proposal_id: str,
    approve: bool,
    *,
    edited_payload: Optional[dict] = None,
    reason: Optional[str] = None,
) -> AiProposal:
    prop = _get_owned(db, owner_id, proposal_id)
    if prop is None:
        raise LookupError("Proposal not found.")
    if prop.status != "PENDING":
        raise ValueError(f"Proposal is already {prop.status}.")
    actor = f"user:{owner_id}"
    mutating = prop.kind in guard.MUTATING_KINDS

    if not approve:
        if mutating and prop.approval_id:
            try:
                approval_service.reject(db, prop.approval_id, int(owner_id), _ws(owner_id), ApprovalReject(reason=reason))
            except HTTPException:
                pass  # already terminal; the proposal is rejected regardless
        prop.status, prop.decided_by, prop.decided_at = "REJECTED", actor, datetime.now(timezone.utc)
        db.commit()
        return prop

    if not mutating:  # informational: acknowledging is not a mutation
        prop.status, prop.decided_by, prop.decided_at = "APPROVED", actor, datetime.now(timezone.utc)
        db.commit()
        return prop
    return _approve_and_run(db, prop, decided_by=actor, edited_payload=edited_payload)


# ------------------------------------------------------------------ inbox reads

def _expire_stale(db: Session, owner_id: str) -> None:
    now = datetime.now(timezone.utc)
    stale = (
        db.query(AiProposal)
        .join(Approval, Approval.id == AiProposal.approval_id)
        .filter(AiProposal.owner_id == owner_id, AiProposal.status == "PENDING", Approval.expires_at <= now)
        .all()
    )
    for p in stale:
        p.status = "EXPIRED"
    if stale:
        db.commit()


def list_proposals(
    db: Session,
    owner_id: str,
    *,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    project_id: Optional[str] = None,
    limit: int = 100,
) -> list[AiProposal]:
    _expire_stale(db, owner_id)
    q = db.query(AiProposal).filter(AiProposal.owner_id == owner_id)
    if status:
        q = q.filter(AiProposal.status == status.upper())
    if kind:
        q = q.filter(AiProposal.kind == kind)
    if project_id:
        q = q.filter(AiProposal.project_id == project_id)
    return q.order_by(AiProposal.created_at.desc()).limit(max(1, min(limit, 200))).all()


def get_proposal(db: Session, owner_id: str, proposal_id: str) -> Optional[AiProposal]:
    _expire_stale(db, owner_id)
    return _get_owned(db, owner_id, proposal_id)
