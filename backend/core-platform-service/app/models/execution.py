import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Index
from app.db.database import Base


class Execution(Base):
    __tablename__ = "executions"

    id = Column(String(64), primary_key=True, default=lambda: f"exec_{uuid.uuid4().hex[:12]}")
    owner_id = Column(String(64), nullable=False, index=True)
    request_id = Column(String(64), nullable=True, index=True)
    idempotency_key = Column(String(128), nullable=True, index=True)

    task_type = Column(String(64), nullable=False, index=True)
    execution_mode = Column(String(32), nullable=False, default="auto")
    status = Column(String(32), nullable=False, default="CREATED", index=True)

    input_json = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)

    provider = Column(String(64), nullable=True)
    model = Column(String(64), nullable=True)

    error_type = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)

    retry_count = Column(Integer, default=0)
    execution_time = Column(Float, default=0.0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_executions_owner_created", "owner_id", "created_at"),
        Index("ix_executions_owner_idempotency", "owner_id", "idempotency_key"),
    )
