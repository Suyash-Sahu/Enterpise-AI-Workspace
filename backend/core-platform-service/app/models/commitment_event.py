"""
Audit event model for Commitment lifecycle mutations and activities.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index

from app.db.database import Base


class CommitmentEvent(Base):
    __tablename__ = "commitment_events"

    id = Column(String(64), primary_key=True, default=lambda: f"cevt_{uuid.uuid4().hex[:10]}")
    commitment_id = Column(String(64), ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, index=True)
    owner_id = Column(String(64), nullable=False, index=True)

    # "created" | "updated" | "status_changed" | "completed" | "dismissed" | "reopened"
    # "deadline_changed" | "owner_changed" | "verified" | "task_linked" | "follow_up_generated"
    event_type = Column(String(64), nullable=False)
    actor_id = Column(String(64), nullable=True)

    # Serialized JSON dict with context and delta
    details = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_commitment_events_commit_created", "commitment_id", "created_at"),
        Index("ix_commitment_events_owner_type", "owner_id", "event_type"),
    )

