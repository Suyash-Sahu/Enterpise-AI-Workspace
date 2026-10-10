"""
Phase 28: DecompositionAttempt persistence model (ATGO v2 telemetry).

Records every decomposition attempt -- accepted or rejected -- with objective hash,
raw completion text, attempt number (1 for initial, 2 for repair), decomposer mode,
and exact rejection reason when rejected.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime, Index
from app.db.database import Base


class DecompositionAttempt(Base):
    __tablename__ = "decomposition_attempts"

    id = Column(String(64), primary_key=True, default=lambda: f"dattempt_{uuid.uuid4().hex[:12]}")
    request_id = Column(String(64), nullable=False, index=True)
    owner_id = Column(String(64), nullable=False, index=True)
    objective_hash = Column(String(64), nullable=False, index=True)
    decomposer_mode = Column(String(32), nullable=False, default="coverage")
    attempt_number = Column(Integer, nullable=False, default=1)

    raw_output = Column(Text, nullable=True)
    accepted = Column(Boolean, nullable=False, default=False)
    rejection_reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_dattempt_owner_obj", "owner_id", "objective_hash"),
    )
