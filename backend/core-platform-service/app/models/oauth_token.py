from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.sql import func

from app.db.base import Base


class OAuthToken(Base):
    """
    A Google OAuth grant.

    At most one row per user may be active: reconnecting deactivates the
    previous grant rather than stacking another row, which is why reads no
    longer have to sort by id and take the newest.
    """

    __tablename__ = "oauth_tokens"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    google_email = Column(String, nullable=False)

    access_token = Column(String, nullable=False)

    refresh_token = Column(String, nullable=False)

    scopes = Column(String, nullable=False)

    # IMPORTANT
    expires_at = Column(
        DateTime(timezone=True),
        nullable=False,
    )

    token_type = Column(
        String,
        default="Bearer",
    )

    is_active = Column(
        Boolean,
        default=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        # Partial unique index: any number of deactivated rows may exist as
        # history, but only one active grant per user.
        Index(
            "uq_oauth_tokens_active_user",
            "user_id",
            unique=True,
            postgresql_where=is_active.is_(True),
            sqlite_where=is_active.is_(True),
        ),
    )