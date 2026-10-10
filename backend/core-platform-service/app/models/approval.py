from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON, TypeDecorator
from app.db.base import Base


class JSONBType(TypeDecorator):
    """
    Uses PostgreSQL JSONB natively, falling back to standard JSON for SQLite.
    """
    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSONB())
        return dialect.type_descriptor(JSON())


class Approval(Base):
    __tablename__ = "approvals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    workspace_id = Column(String(64), nullable=False, index=True)
    execution_id = Column(String(64), nullable=True, index=True)

    action_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default="pending", index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    payload = Column(JSONBType, nullable=False)
    edited_payload = Column(JSONBType, nullable=True)

    risk_level = Column(String(32), nullable=False, default="high")

    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    rejected_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
    )
