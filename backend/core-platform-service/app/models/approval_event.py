from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func
from app.db.base import Base
from app.models.approval import JSONBType


class ApprovalEvent(Base):
    __tablename__ = "approval_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    approval_id = Column(Integer, ForeignKey("approvals.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    event_type = Column(String(64), nullable=False)
    old_status = Column(String(32), nullable=True)
    new_status = Column(String(32), nullable=False)

    metadata_json = Column(JSONBType, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
