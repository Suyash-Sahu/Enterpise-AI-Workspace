"""
Persistent execution tracking models for Commitment Intelligence scans and sweeps.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from app.db.database import Base


class CommitmentRun(Base):
    __tablename__ = "commitment_runs"

    id = Column(String(64), primary_key=True, default=lambda: f"crun_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)

    # "scan" | "sweep"
    run_type = Column(String(32), nullable=False, default="scan")
    # "queued" | "running" | "completed" | "completed_with_warnings" | "failed" | "cancelled"
    status = Column(String(32), nullable=False, default="queued", index=True)
    current_stage = Column(String(64), nullable=True)
    progress_percent = Column(Integer, nullable=False, default=0)

    total_items = Column(Integer, nullable=False, default=0)
    processed_items = Column(Integer, nullable=False, default=0)
    successful_items = Column(Integer, nullable=False, default=0)
    failed_items = Column(Integer, nullable=False, default=0)

    commitments_found = Column(Integer, nullable=False, default=0)
    created_count = Column(Integer, nullable=False, default=0)
    updated_count = Column(Integer, nullable=False, default=0)

    # Serialized JSON lists / dicts for persistence
    warnings = Column(Text, nullable=True)
    errors = Column(Text, nullable=True)
    result_summary = Column(Text, nullable=True)

    cancel_requested = Column(Boolean, nullable=False, default=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    stages = relationship(
        "CommitmentRunStage",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="CommitmentRunStage.stage_order",
    )

    __table_args__ = (
        Index("ix_commitment_runs_owner_status", "owner_id", "status"),
        Index("ix_commitment_runs_owner_created", "owner_id", "created_at"),
    )


class CommitmentRunStage(Base):
    __tablename__ = "commitment_run_stages"

    id = Column(String(64), primary_key=True, default=lambda: f"crstg_{uuid.uuid4().hex[:10]}")
    run_id = Column(String(64), ForeignKey("commitment_runs.id", ondelete="CASCADE"), nullable=False, index=True)

    stage_name = Column(String(64), nullable=False)
    stage_order = Column(Integer, nullable=False, default=0)
    # "pending" | "running" | "completed" | "failed" | "skipped"
    status = Column(String(32), nullable=False, default="pending")
    progress_percent = Column(Integer, nullable=False, default=0)
    processed_count = Column(Integer, nullable=False, default=0)
    total_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    run = relationship("CommitmentRun", back_populates="stages")

