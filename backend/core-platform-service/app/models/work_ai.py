"""
AMOF Work AI layer models (PRD v3 §6.3/§6.4).

TENANCY NOTE: AMOF Work has no organization/membership/RBAC system. The
effective tenant boundary is the authenticated user (owner_id), exactly as in
WorkGraph. The PRD's "organization_id"/"org-level kill switch" are therefore
implemented as owner-level (per-user) here. This is per-user isolation, NOT
real multi-tenant organizations; a future org model would replace owner_id.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, Index, Integer, String, Text, UniqueConstraint

from app.db.database import Base
from app.models.approval import JSONBType


def _now():
    return datetime.now(timezone.utc)


class AiProposal(Base):
    """
    Every agent output that could change state (or that the user should
    review) lands here. Agents never write WorkGraph directly.

    kind:   create_item | update_item | link_items      (mutating -> Approval)
            duplicate_warning | risk_alert | sprint_plan (informational)
    status: PENDING -> APPROVED -> EXECUTED | FAILED
            PENDING -> REJECTED | EXPIRED | CANCELLED (kill switch)
            (PRD lists PENDING/APPROVED/REJECTED/EXPIRED; EXECUTED/FAILED/CANCELLED
            are additions so execution outcome and kill-switch revocation are visible.)
    """
    __tablename__ = "ai_proposals"

    id = Column(String(64), primary_key=True, default=lambda: f"prop_{uuid.uuid4().hex[:12]}")
    owner_id = Column(String(64), nullable=False, index=True)
    # Server-derived (verified against owner_id) -- never taken from the client.
    project_id = Column(String(64), nullable=True, index=True)

    kind = Column(String(32), nullable=False, index=True)
    agent = Column(String(48), nullable=False)
    payload = Column(JSONBType, nullable=False)

    source = Column(String(32), nullable=False)          # user_command | capture | risk_scan | ...
    source_ref = Column(String(64), nullable=True)
    status = Column(String(16), nullable=False, default="PENDING", index=True)
    confidence = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)

    privacy_tier = Column(String(16), nullable=True)
    autonomy_level = Column(String(2), nullable=False, default="L1")

    # The one authoritative approval record (mutating kinds only).
    approval_id = Column(Integer, nullable=True, index=True)
    result = Column(JSONBType, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now)
    decided_at = Column(DateTime(timezone=True), nullable=True)
    decided_by = Column(String(96), nullable=True)       # user:<id> | autonomy:L3:<project>:<kind> | kill_switch

    __table_args__ = (Index("ix_ai_proposals_owner_status", "owner_id", "status"),)


class WorkAutonomyGrant(Base):
    """Per-(project, action_kind) autonomy level. Absent row == L1. Never global."""
    __tablename__ = "work_autonomy_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), nullable=False, index=True)
    project_id = Column(String(64), nullable=False)
    action_kind = Column(String(32), nullable=False)
    level = Column(String(2), nullable=False, default="L1")
    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (UniqueConstraint("owner_id", "project_id", "action_kind", name="uq_autonomy_scope"),)


class WorkAiSetting(Base):
    """
    Kill switch. project_id == "" is the user-level switch (the PRD's
    "org-level" toggle); otherwise it is the per-project switch. Absent row == ON.
    """
    __tablename__ = "work_ai_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), nullable=False, index=True)
    project_id = Column(String(64), nullable=False, default="")
    ai_enabled = Column(Boolean, nullable=False, default=True)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)
    updated_by = Column(String(96), nullable=True)

    __table_args__ = (UniqueConstraint("owner_id", "project_id", name="uq_ai_setting_scope"),)


# ---------------------------------------------------------------------------
# Rule-based automations (PRD v3 §7.1). Distinct from app/models/automation.py,
# which stores supervisor *plan* templates: these are trigger/condition/action
# rules over work items. Scheduling reuses the existing Celery beat (one tick
# entry); there is no second scheduler.
# ---------------------------------------------------------------------------

class WorkAutomation(Base):
    """
    status: draft -> (preview) -> active <-> paused. A rule can only become active
    when `previewed_hash == definition_hash`, i.e. its *current* definition was
    dry-run. Editing is not supported: a changed rule is a new rule.
    """
    __tablename__ = "work_automations"

    id = Column(String(64), primary_key=True, default=lambda: f"wauto_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)
    project_id = Column(String(64), nullable=True, index=True)      # None == all of the owner's projects
    name = Column(String(255), nullable=False)
    source_text = Column(Text, nullable=True)                        # the NL sentence, kept for the audit trail

    trigger = Column(JSONBType, nullable=False)
    conditions = Column(JSONBType, nullable=False)
    actions = Column(JSONBType, nullable=False)

    status = Column(String(16), nullable=False, default="draft", index=True)
    definition_hash = Column(String(64), nullable=False)
    previewed_hash = Column(String(64), nullable=True)
    previewed_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    # Highest work_item_activity.id already evaluated for event triggers.
    cursor = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=_now)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now)


class WorkAutomationRun(Base):
    """One evaluation that found work (or was refused). Blocked/limited runs are rows too -- they are the audit."""
    __tablename__ = "work_automation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    automation_id = Column(String(64), nullable=False, index=True)
    owner_id = Column(String(64), nullable=False, index=True)
    # completed | partial | blocked_blast_radius | rate_limited | halted_kill_switch | failed
    status = Column(String(24), nullable=False)
    matched_count = Column(Integer, nullable=False, default=0)
    proposals_created = Column(Integer, nullable=False, default=0)
    executed_count = Column(Integer, nullable=False, default=0)
    detail = Column(JSONBType, nullable=True)
    error = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=_now, index=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)


class WorkAutomationFired(Base):
    """(rule, item, trigger occurrence) fires at most once -- the loop/duplicate guard."""
    __tablename__ = "work_automation_fired"

    id = Column(Integer, primary_key=True, autoincrement=True)
    automation_id = Column(String(64), nullable=False, index=True)
    task_id = Column(String(64), nullable=False)
    trigger_key = Column(String(96), nullable=False)
    outcome = Column(String(16), nullable=False)      # proposed | executed | blocked | error
    created_at = Column(DateTime(timezone=True), default=_now)

    __table_args__ = (UniqueConstraint("automation_id", "task_id", "trigger_key", name="uq_automation_fired"),)
