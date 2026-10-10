"""
AMOF Work AI guard: kill switch + autonomy policy (PRD v3 §6.3, §6.4).

Owner-level tenancy: the PRD's "org-level" switch is the per-user switch here
(no organization model exists; see app/models/work_ai.py).

Enforcement points (all server-side, all fail closed):
  * pipeline.create_proposal / decide        -> assert_enabled()
  * execution handlers (work_handlers.py)    -> assert_enabled() again at the
    moment of mutation, so a proposal approved *before* the switch flipped
    cannot execute after it.
  * an already-running mutation is never aborted; the *next* checkpoint fails.
"""
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from app.models.work_ai import AiProposal, WorkAiSetting, WorkAutonomyGrant
from app.services.audit_service import log_action
from app.services.workgraph_service import workgraph_service

logger = logging.getLogger(__name__)

LEVELS = ("L0", "L1", "L2", "L3")
DEFAULT_LEVEL = "L1"

# action kind -> approval-gated capability that performs it.
MUTATING_KINDS: dict[str, str] = {
    "create_item": "work.create_item",
    "update_item": "work.update_item",
    "link_items": "work.link_items",
}
# Read-only outputs that still land in the AI Inbox for review.
INFORMATIONAL_KINDS = frozenset({"duplicate_warning", "risk_alert", "sprint_plan", "notification"})
ALL_KINDS = frozenset(MUTATING_KINDS) | INFORMATIONAL_KINDS

# Hard L3 denylist by *name*, independent of registry metadata: anything that
# deletes, sends, posts externally or acts in bulk is never auto-executable,
# even if a bad grant row exists in the database.
_L3_FORBIDDEN_TOKENS = ("delete", "remove", "destroy", "purge", "bulk", "send", "post", "external", "irreversible")


class KillSwitchOff(Exception):
    """AI Work automation is switched off for this scope."""


class AutonomyViolation(Exception):
    """An action tried to run at an autonomy level its kind is not eligible for."""


# Hooks other components (automation runner) register so a kill-switch flip
# can also cancel their queued work. Called as hook(db, owner_id, project_id).
_kill_hooks: list[Callable[[Session, str, Optional[str]], int]] = []


def register_kill_hook(fn: Callable[[Session, str, Optional[str]], int]) -> None:
    if fn not in _kill_hooks:
        _kill_hooks.append(fn)


def _audit(db: Session, owner_id: str, action: str) -> None:
    try:
        log_action(db=db, user_id=int(owner_id), action=action, endpoint="/workgraph/ai", method="POLICY")
    except Exception:
        db.rollback()
        logger.exception("[WorkAI] audit write failed for %s", action)


# --------------------------------------------------------------------- kill switch

def is_enabled(db: Session, owner_id: str, project_id: Optional[str] = None) -> bool:
    """ON unless the user-level switch or (when given) the project switch is OFF."""
    scopes = [""] + ([project_id] if project_id else [])
    off = (
        db.query(WorkAiSetting.id)
        .filter(
            WorkAiSetting.owner_id == owner_id,
            WorkAiSetting.project_id.in_(scopes),
            WorkAiSetting.ai_enabled.is_(False),
        )
        .first()
    )
    return off is None


def assert_enabled(db: Session, owner_id: str, project_id: Optional[str] = None) -> None:
    if not is_enabled(db, owner_id, project_id):
        raise KillSwitchOff("AI Work Automation is switched OFF; no AI mutations or automation runs are allowed.")


def cancel_pending(db: Session, owner_id: str, project_id: Optional[str] = None) -> int:
    """
    Revoke every not-yet-executed proposal in scope (and its Approval), then
    let registered hooks (automation runs) do the same. Executed work is untouched.
    """
    from app.services.approval.approval_service import approval_service  # local: avoid import cycle

    q = db.query(AiProposal).filter(AiProposal.owner_id == owner_id, AiProposal.status == "PENDING")
    if project_id:
        q = q.filter(AiProposal.project_id == project_id)
    cancelled = 0
    for prop in q.all():
        prop.status = "CANCELLED"
        prop.decided_by = "kill_switch"
        prop.decided_at = datetime.now(timezone.utc)
        if prop.approval_id:
            try:
                approval_service.reject(db, prop.approval_id, int(owner_id), f"ws_user_{owner_id}")
            except Exception:  # already terminal/expired: proposal is cancelled regardless
                logger.info("[WorkAI] approval %s not rejectable during kill switch", prop.approval_id)
        cancelled += 1
    db.commit()
    for hook in _kill_hooks:
        try:
            cancelled += hook(db, owner_id, project_id)
        except Exception:
            logger.exception("[WorkAI] kill-switch hook failed")
    return cancelled


def set_enabled(
    db: Session, owner_id: str, enabled: bool, project_id: Optional[str] = None, actor: Optional[str] = None
) -> dict:
    if project_id and workgraph_service.get_project(db, owner_id, project_id) is None:
        raise ValueError("Project not found.")
    scope = project_id or ""
    row = (
        db.query(WorkAiSetting)
        .filter(WorkAiSetting.owner_id == owner_id, WorkAiSetting.project_id == scope)
        .first()
    )
    if row is None:
        row = WorkAiSetting(owner_id=owner_id, project_id=scope)
        db.add(row)
    row.ai_enabled = enabled
    row.updated_by = actor or f"user:{owner_id}"
    db.commit()
    _audit(db, owner_id, f"work.ai_switch:{scope or 'user'}:{'on' if enabled else 'off'}")

    cancelled = 0 if enabled else cancel_pending(db, owner_id, project_id)
    return {"scope": scope or "user", "ai_enabled": enabled, "cancelled": cancelled}


def get_switches(db: Session, owner_id: str) -> dict:
    rows = db.query(WorkAiSetting).filter(WorkAiSetting.owner_id == owner_id).all()
    return {
        "user": next((r.ai_enabled for r in rows if r.project_id == ""), True),
        "projects": {r.project_id: r.ai_enabled for r in rows if r.project_id},
    }


# --------------------------------------------------------------------- autonomy

def l3_eligible(kind: str) -> bool:
    """
    Whether `kind` may EVER run at L3. Evaluated from the capability's own
    declared metadata plus a name denylist, and re-checked at execution time
    (pipeline._auto_execute) -- so a bad grant row cannot enable a destructive action.
    """
    from app.execution.registry import task_registry  # lazy: registry imports the work handlers

    cap = MUTATING_KINDS.get(kind)
    if cap is None or any(tok in kind for tok in _L3_FORBIDDEN_TOKENS):
        return False
    try:
        meta = task_registry.get_metadata(cap)
    except ValueError:
        return False
    return meta.side_effect == "reversible_write" and meta.risk_level in ("low", "medium")


def effective_level(db: Session, owner_id: str, project_id: Optional[str], kind: str) -> str:
    """L1 unless an explicit per-(project, kind) grant says otherwise. Never global."""
    if not project_id:
        return DEFAULT_LEVEL
    row = (
        db.query(WorkAutonomyGrant.level)
        .filter(
            WorkAutonomyGrant.owner_id == owner_id,
            WorkAutonomyGrant.project_id == project_id,
            WorkAutonomyGrant.action_kind == kind,
        )
        .first()
    )
    return row[0] if row and row[0] in LEVELS else DEFAULT_LEVEL


def set_grant(db: Session, owner_id: str, project_id: str, kind: str, level: str, actor: Optional[str] = None) -> dict:
    if level not in LEVELS:
        raise ValueError("Invalid autonomy level.")
    if kind not in MUTATING_KINDS:
        raise ValueError("Autonomy can only be set for mutating action kinds.")
    if workgraph_service.get_project(db, owner_id, project_id) is None:
        raise ValueError("Project not found.")
    if level == "L3" and not l3_eligible(kind):
        raise ValueError(f"Action kind '{kind}' is not eligible for L3 (destructive/high-risk actions never auto-execute).")

    old = effective_level(db, owner_id, project_id, kind)
    row = (
        db.query(WorkAutonomyGrant)
        .filter(
            WorkAutonomyGrant.owner_id == owner_id,
            WorkAutonomyGrant.project_id == project_id,
            WorkAutonomyGrant.action_kind == kind,
        )
        .first()
    )
    if level == DEFAULT_LEVEL:  # back to default == revoke
        if row is not None:
            db.delete(row)
            db.commit()
        _audit(db, owner_id, f"work.autonomy.revoke:{project_id}:{kind}:{old}->{DEFAULT_LEVEL}")
    else:
        if row is None:
            row = WorkAutonomyGrant(owner_id=owner_id, project_id=project_id, action_kind=kind)
            db.add(row)
        row.level = level
        db.commit()
        verb = "grant" if old == DEFAULT_LEVEL else "modify"
        _audit(db, owner_id, f"work.autonomy.{verb}:{project_id}:{kind}:{old}->{level}")
    return {"project_id": project_id, "action_kind": kind, "level": level}


def list_grants(db: Session, owner_id: str) -> list[WorkAutonomyGrant]:
    return db.query(WorkAutonomyGrant).filter(WorkAutonomyGrant.owner_id == owner_id).all()
