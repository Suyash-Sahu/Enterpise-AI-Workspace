from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from app.db.base import Base
from app.utils.timeutils import utcnow_naive


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(100), nullable=False)

    email = Column(String(255), unique=True, nullable=False, index=True)

    password_hash = Column(String(255), nullable=False)

    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)

    created_at = Column(DateTime, default=utcnow_naive)

    updated_at = Column(
        DateTime,
        default=utcnow_naive,
        onupdate=utcnow_naive,
    )

    role = relationship("Role", back_populates="users")

    sessions = relationship("Session", back_populates="user")

    audit_logs = relationship("AuditLog", back_populates="user")