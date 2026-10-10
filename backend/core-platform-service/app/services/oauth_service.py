from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.models.oauth_state import PURPOSE_CONNECT, OAuthState

# An authorisation round-trip takes seconds. Anything older is either an
# abandoned attempt or a replay.
OAUTH_STATE_TTL_MINUTES = 10


def save_oauth_state(
    db: Session,
    state: str,
    verifier: str,
    user_id: Optional[int] = None,
    purpose: str = PURPOSE_CONNECT,
) -> OAuthState:
    """
    Record an authorisation attempt.

    `user_id` is None for sign-in, where the user is not known until Google
    answers. `purpose` is checked at the callback so the two flows cannot
    redeem each other's state.
    """
    obj = OAuthState(
        state=state,
        code_verifier=verifier,
        user_id=user_id,
        purpose=purpose,
        expires_at=datetime.now(timezone.utc)
        + timedelta(minutes=OAUTH_STATE_TTL_MINUTES),
    )

    db.add(obj)
    db.commit()
    db.refresh(obj)

    return obj


def consume_oauth_state(
    db: Session,
    state: str,
    expected_purpose: Optional[str] = None,
) -> Optional[OAuthState]:
    """
    Fetch and immediately delete a state row, returning it only if unexpired.

    Deleting on read makes the state single-use: a replayed callback finds
    nothing, so an intercepted authorization code cannot be redeemed twice.
    The detached instance stays readable for the caller after deletion.
    """
    obj = (
        db.query(OAuthState)
        .filter(OAuthState.state == state)
        .first()
    )

    if obj is None:
        return None

    expired = obj.is_expired()

    # Expire the object into a plain snapshot before the row disappears.
    snapshot = OAuthState(
        state=obj.state,
        code_verifier=obj.code_verifier,
        user_id=obj.user_id,
        purpose=obj.purpose,
        expires_at=obj.expires_at,
    )

    # The row is destroyed either way: a state presented to the wrong callback
    # is burned rather than left for a second attempt.
    db.delete(obj)
    db.commit()

    if expired:
        return None

    if expected_purpose is not None and snapshot.purpose != expected_purpose:
        return None

    return snapshot


def purge_expired_oauth_states(db: Session) -> int:
    """Drop abandoned authorisation attempts so the table cannot grow forever."""
    deleted = (
        db.query(OAuthState)
        .filter(OAuthState.expires_at <= datetime.now(timezone.utc))
        .delete(synchronize_session=False)
    )

    db.commit()

    return deleted
