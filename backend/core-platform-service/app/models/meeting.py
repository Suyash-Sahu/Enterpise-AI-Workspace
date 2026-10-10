"""
Meeting models (AMOF-X Phase 7): Meeting/MeetingActionItem.

No live Google Meet transcript-export API exists for third-party apps (a
confirmed external constraint, not an oversight -- see PHASE_07.md), so
`transcript_source` records how the text actually arrived (upload,
note-taking-tool export, manual paste) rather than claiming a live capture
path that doesn't exist.

Tenant-scoped by owner_id, the same opaque-tenant-string convention as
Project/Task (app/models/workgraph.py) and Execution/WorkflowPlan.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(String(64), primary_key=True, default=lambda: f"meet_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)

    # "upload" | "note_taking_export" | "manual_paste"
    transcript_source = Column(String(32), nullable=False, default="manual_paste")
    transcript_text = Column(Text, nullable=False)

    summary = Column(Text, nullable=True)
    # Full structured extraction (decisions/risks/unresolved_questions/etc.)
    # as JSON text -- summary and action_items are also normalized out for
    # direct querying, but this keeps the complete extraction retrievable
    # without inventing a column per field the model might return.
    extraction_json = Column(Text, nullable=True)

    # "pending" | "processed" | "failed"
    status = Column(String(16), nullable=False, default="pending", index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    action_items = relationship("MeetingActionItem", back_populates="meeting")

    __table_args__ = (
        Index("ix_meetings_owner_created", "owner_id", "created_at"),
    )


class MeetingActionItem(Base):
    __tablename__ = "meeting_action_items"

    id = Column(String(64), primary_key=True, default=lambda: f"mai_{uuid.uuid4().hex[:10]}")
    meeting_id = Column(String(64), ForeignKey("meetings.id"), nullable=False, index=True)

    description = Column(Text, nullable=False)
    owner = Column(String(255), nullable=True)
    # Free-text as extracted ("next Friday", "2026-09-20", "EOW") -- the
    # source is an LLM extraction from prose, not a form field, so forcing a
    # real DateTime here would mean silently dropping or mis-parsing
    # deadlines the model expressed in a way a strict parser rejects.
    due_date = Column(String(128), nullable=True)

    # Set only when the explicit opt-in task-creation endpoint has been
    # called for this item -- extraction alone never populates this.
    workgraph_task_id = Column(String(64), ForeignKey("tasks.id"), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    meeting = relationship("Meeting", back_populates="action_items")
