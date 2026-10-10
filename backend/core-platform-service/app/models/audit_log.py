
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.utils.timeutils import utcnow_naive


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    action = Column(String(255), nullable=False)

    endpoint = Column(String(255), nullable=False)

    method = Column(String(20), nullable=False)

    created_at = Column(
        DateTime,
        default=utcnow_naive,
    )

    user = relationship("User", back_populates="audit_logs")