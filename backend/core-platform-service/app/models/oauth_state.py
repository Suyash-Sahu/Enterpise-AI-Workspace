from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from app.db.base import Base


# The two kinds of Google round trip this table serves.
PURPOSE_SIGNIN = "signin"
PURPOSE_CONNECT = "connect"


class OAuthState(Base):
    """
    A single in-flight Google OAuth authorisation attempt.

    Given a short TTL and consumed on read, so a state value cannot be minted
    by one party and redeemed by another (or redeemed months later).

    A `connect` attempt is bound to the signed-in user who started it. A
    `signin` attempt has no user yet — working out who the user is is the
    point of the round trip — so user_id is null there. Each callback checks
    `purpose`, so a state minted for signing in cannot be redeemed at the
    connector callback and land a Google grant on the wrong account.
    """

    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, index=True)

    state = Column(String, unique=True, nullable=False, index=True)

    code_verifier = Column(String, nullable=False)

    # Null for sign-in attempts, set for connector attempts.
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

    purpose = Column(
        String(16),
        nullable=False,
        default=PURPOSE_CONNECT,
        server_default=PURPOSE_CONNECT,
        index=True,
    )

    expires_at = Column(DateTime(timezone=True), nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    def is_expired(self, now: datetime | None = None) -> bool:
        now = now or datetime.now(timezone.utc)
        expires_at = self.expires_at

        if expires_at is None:
            return True

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        return expires_at <= now
