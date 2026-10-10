"""
Chat conversations, owned by a user and stored in the database.

Finding C11: these lived in a module-level dict keyed only by session id, with
no user column anywhere in the file. Every signed-in account therefore shared
one store — any user could list, read and delete any other user's
conversations — and the whole history was lost on restart.

Ownership is now a foreign key, and every query filters on it. A session id is
not a capability: knowing one grants nothing without owning the row.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON

from app.db.base import Base

# JSONB on Postgres, plain JSON elsewhere, so the SQLite fallback still works.
JSONType = JSON().with_variant(JSONB(), "postgresql")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ChatSession(Base):
    """One conversation, belonging to exactly one user."""

    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True)

    # Public identifier used in URLs. Opaque and unguessable, but ownership is
    # still checked on every access — this is not a bearer token.
    public_id = Column(String(48), nullable=False, unique=True, index=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    title = Column(String(200), nullable=False, default="New Conversation")

    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at = Column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    messages = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.id",
    )

    __table_args__ = (
        Index("ix_chat_sessions_user_updated", "user_id", "updated_at"),
    )


class ChatMessage(Base):
    """A single turn. Ordered by insertion, which is conversation order."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True)

    public_id = Column(String(48), nullable=False, unique=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Denormalised so a message cannot be read without an ownership check even
    # if a future query forgets to join through the session.
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    role = Column(String(16), nullable=False)

    content = Column(Text, nullable=False, default="")

    # Which capability answered, and which runtime actually ran it. Null when
    # not known — never a guess. Previously the provider was inferred from the
    # agent name and reported as fact.
    agent = Column(String(64), nullable=True)
    provider = Column(String(64), nullable=True)
    runtime = Column(String(16), nullable=True)
    execution_id = Column(String(64), nullable=True)

    # Citations actually produced by retrieval. Empty when there are none;
    # this column previously carried an invented Drive file on every answer.
    sources = Column(JSONType, nullable=False, default=list)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_utcnow)

    session = relationship("ChatSession", back_populates="messages")
