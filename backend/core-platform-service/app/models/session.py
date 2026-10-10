from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    """
    One row per issued refresh token.

    Rotation model: each refresh mints a new row in the same `family_id` and
    marks the previous row consumed. Presenting an already-consumed token means
    it leaked, so the entire family is revoked.
    """

    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # SHA-256 of the refresh token — the raw token is never stored.
    token_hash = Column(String(64), nullable=False, unique=True, index=True)

    # JWT id of the refresh token this row represents.
    jti = Column(String(64), nullable=False, unique=True, index=True)

    # Shared by every token descended from a single login.
    family_id = Column(String(64), nullable=False, index=True)

    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Set when this token is exchanged for a new one. A consumed token that is
    # presented again is a replay.
    consumed_at = Column(DateTime(timezone=True), nullable=True)

    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Distinguishes "revoked because rotated/logged out" from "revoked because
    # we detected reuse", which is worth alerting on.
    revoked_reason = Column(String(64), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow)

    user = relationship("User", back_populates="sessions")

    __table_args__ = (
        Index("ix_sessions_user_active", "user_id", "is_active"),
    )

    def is_usable(self, now: datetime | None = None) -> bool:
        now = now or _utcnow()
        expires_at = self.expires_at

        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return (
            self.is_active
            and self.revoked_at is None
            and self.consumed_at is None
            and expires_at is not None
            and expires_at > now
        )
