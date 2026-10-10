"""
Commitment model: tracked promises/commitments detected from Gmail messages
and meeting action items.

Mirrors app/models/meeting.py's shape (owner-scoped, free-text due_date since
the source is prose an LLM extracted from, not a form field). Deliberately a
read/track-only row: nothing here creates a WorkGraph task. `linked_task_id`
is populated only when a task already exists for this commitment (a meeting
action item that was separately, explicitly converted via the existing
create-task endpoints) -- the commitment tracker observes that link, it never
creates one.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, UniqueConstraint
from app.db.database import Base


class Commitment(Base):
    __tablename__ = "commitments"

    id = Column(String(64), primary_key=True, default=lambda: f"commit_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)

    description = Column(Text, nullable=False)
    responsible_party = Column(String(255), nullable=True)
    # Free-text as extracted ("by Friday", "2026-09-20") -- same reasoning as
    # MeetingActionItem.due_date: an LLM extraction from prose, not a form field.
    due_date = Column(String(128), nullable=True)

    # "gmail" | "meeting"
    source_type = Column(String(16), nullable=False)
    # A Gmail message id or a meeting_action_items.id -- the dedupe key
    # together with (owner_id, source_type), so a rescan updates the same
    # row instead of creating a duplicate.
    source_ref = Column(String(128), nullable=False)

    # "pending" | "completed" | "at_risk" -- recomputed on every scan from
    # linked_task_id/due_date, never hand-set.
    status = Column(String(16), nullable=False, default="pending", index=True)
    linked_task_id = Column(String(64), ForeignKey("tasks.id"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "source_type", "source_ref", name="uq_commitment_source"),
        Index("ix_commitments_owner_status", "owner_id", "status"),
    )
