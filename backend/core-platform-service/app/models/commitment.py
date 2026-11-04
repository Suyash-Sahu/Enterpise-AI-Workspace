"""
Commitment model: tracked promises/commitments detected from Gmail messages,
meeting action items, and manual operational entries.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Index, UniqueConstraint, Float, Boolean
from app.db.database import Base


class Commitment(Base):
    __tablename__ = "commitments"

    id = Column(String(64), primary_key=True, default=lambda: f"commit_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)

    description = Column(Text, nullable=False)
    responsible_party = Column(String(255), nullable=True)
    # Counterparty: person/party owed
    counterparty = Column(String(255), nullable=True)
    # Direction: "owed_by_me" | "owed_to_me" | "mutual" | "unknown"
    direction = Column(String(32), nullable=False, default="owed_by_me")

    # Free-text as extracted ("by Friday", "2026-09-20")
    due_date = Column(String(128), nullable=True)
    original_due_date_text = Column(String(255), nullable=True)
    # Parsed normalized UTC timestamp
    normalized_due_date = Column(DateTime, nullable=True, index=True)
    timezone = Column(String(64), nullable=True, default="UTC")

    # Confidence score (0.0 to 1.0)
    confidence = Column(Float, nullable=True, default=1.0)
    # Supporting evidence excerpt
    evidence = Column(Text, nullable=True)
    # Priority: "low" | "medium" | "high"
    priority = Column(String(16), nullable=False, default="medium")

    # "gmail" | "meeting" | "manual"
    source_type = Column(String(16), nullable=False)
    # Gmail message ID, meeting action item ID, or manual ID
    source_ref = Column(String(128), nullable=False)
    # Serialized JSON metadata (subject, email sender, snippet, meeting title)
    source_metadata = Column(Text, nullable=True)

    # Lifecycle status: "pending" | "completed" | "dismissed"
    # Note: "at_risk" and "overdue" are derived dynamically from normalized_due_date / linked task
    status = Column(String(16), nullable=False, default="pending", index=True)
    linked_task_id = Column(String(64), ForeignKey("tasks.id"), nullable=True)

    # Verification state: "unverified" | "verification_pending" | "verified" | "rejected"
    verification_status = Column(String(32), nullable=False, default="unverified")
    verification_evidence = Column(Text, nullable=True)
    verification_reasoning = Column(Text, nullable=True)

    review_required = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "source_type", "source_ref", name="uq_commitment_source"),
        Index("ix_commitments_owner_status", "owner_id", "status"),
        Index("ix_commitments_owner_direction", "owner_id", "direction"),
        Index("ix_commitments_owner_due", "owner_id", "normalized_due_date"),
    )
