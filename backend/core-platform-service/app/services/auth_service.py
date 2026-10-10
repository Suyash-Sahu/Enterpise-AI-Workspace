import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    create_refresh_token,
    dummy_verify,
    generate_token_family_id,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
    verify_token,
)
from app.models.role import Role
from app.models.session import Session as UserSession
from app.models.user import User
from app.schemas.auth import LoginRequest, SignupRequest

logger = logging.getLogger(__name__)

# Deliberately identical for "no such user" and "wrong password" so the
# response cannot be used to enumerate accounts.
INVALID_CREDENTIALS = "Invalid email or password"

DEFAULT_ROLE_NAME = "user"


class AuthError(ValueError):
    """Raised for any recoverable authentication failure."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_default_role(db: Session) -> Role:
    role = db.query(Role).filter(Role.name == DEFAULT_ROLE_NAME).first()

    if role is None:
        # Seeded by app.db.seed.seed_roles; a missing role is a deployment
        # fault, not something the caller can fix.
        raise AuthError("Default role is not configured")

    return role


def _issue_token_pair(
    db: Session,
    user: User,
    family_id: Optional[str] = None,
) -> dict:
    """
    Mint an access/refresh pair and persist the refresh token's identity.

    Committing the session row before returning means a token is never handed
    out that the server cannot subsequently revoke.
    """
    access_token, _, access_expires = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role.name if user.role else DEFAULT_ROLE_NAME,
        }
    )

    refresh_token, refresh_jti, refresh_expires = create_refresh_token(
        {"sub": str(user.id)}
    )

    db.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            jti=refresh_jti,
            family_id=family_id or generate_token_family_id(),
            expires_at=refresh_expires,
            is_active=True,
        )
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_at": access_expires,
    }


def _revoke_family(
    db: Session,
    family_id: str,
    reason: str,
) -> None:
    now = _utcnow()

    db.query(UserSession).filter(
        UserSession.family_id == family_id,
        UserSession.is_active.is_(True),
    ).update(
        {
            UserSession.is_active: False,
            UserSession.revoked_at: now,
            UserSession.revoked_reason: reason,
        },
        synchronize_session=False,
    )


def signup_user(db: Session, request: SignupRequest) -> User:
    existing_user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if existing_user:
        raise AuthError("Email already exists")

    role = _get_default_role(db)

    user = User(
        name=request.name,
        email=request.email,
        password_hash=hash_password(request.password),
        role_id=role.id,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def login_user(db: Session, request: LoginRequest) -> dict:
    user = (
        db.query(User)
        .filter(User.email == request.email)
        .first()
    )

    if user is None:
        # Spend the same time we would have spent verifying a real hash.
        dummy_verify()
        raise AuthError(INVALID_CREDENTIALS)

    if not verify_password(request.password, user.password_hash):
        raise AuthError(INVALID_CREDENTIALS)

    # Upgrade legacy bcrypt (and outdated argon2) hashes now that we hold the
    # plaintext. Nobody has to reset a password for the migration to complete.
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(request.password)
        logger.info("Upgraded password hash for user_id=%s", user.id)

    tokens = _issue_token_pair(db, user)
    db.commit()

    return tokens


def login_or_register_google_user(
    db: Session,
    email: str,
    name: str,
) -> dict:
    """
    Exchange a Google identity that has already been verified server-side for a
    backend token pair, creating the user on first sight.

    The caller is responsible for having verified the identity with Google;
    this function never sees a Google token.
    """
    user = db.query(User).filter(User.email == email).first()

    if user is None:
        role = _get_default_role(db)
        user = User(
            name=name or email.split("@")[0],
            email=email,
            # Google-only accounts get an unusable random password rather than
            # a blank or predictable one, so /auth/login can never match it.
            password_hash=hash_password(secrets.token_urlsafe(48)[:64]),
            role_id=role.id,
        )
        db.add(user)
        db.flush()

    tokens = _issue_token_pair(db, user)
    db.commit()

    return tokens


def refresh_access_token(db: Session, refresh_token: str) -> dict:
    payload = verify_token(refresh_token, expected_type="refresh")

    if payload is None:
        raise AuthError("Invalid refresh token")

    session = (
        db.query(UserSession)
        .filter(UserSession.token_hash == hash_token(refresh_token))
        .first()
    )

    if session is None:
        raise AuthError("Invalid refresh token")

    # Replay: this token was already exchanged. Assume it leaked and take down
    # every token descended from the same login.
    if session.consumed_at is not None or not session.is_active:
        logger.warning(
            "Refresh token reuse detected for user_id=%s family_id=%s; "
            "revoking token family",
            session.user_id,
            session.family_id,
        )
        _revoke_family(db, session.family_id, reason="reuse_detected")
        db.commit()
        raise AuthError("Invalid refresh token")

    if not session.is_usable():
        raise AuthError("Refresh token expired")

    user = db.query(User).filter(User.id == session.user_id).first()

    if user is None:
        _revoke_family(db, session.family_id, reason="user_missing")
        db.commit()
        raise AuthError("Invalid refresh token")

    now = _utcnow()
    session.consumed_at = now
    session.is_active = False
    session.revoked_at = now
    session.revoked_reason = "rotated"

    tokens = _issue_token_pair(db, user, family_id=session.family_id)
    db.commit()

    return tokens


def logout_user(db: Session, refresh_token: Optional[str], user: User) -> None:
    """
    Revoke server-side session state.

    With a refresh token, only that login's family is revoked so other devices
    stay signed in. Without one, every active session for the user is revoked.
    """
    if refresh_token:
        session = (
            db.query(UserSession)
            .filter(UserSession.token_hash == hash_token(refresh_token))
            .first()
        )

        if session is not None and session.user_id == user.id:
            _revoke_family(db, session.family_id, reason="logout")
            db.commit()
            return

    now = _utcnow()
    db.query(UserSession).filter(
        UserSession.user_id == user.id,
        UserSession.is_active.is_(True),
    ).update(
        {
            UserSession.is_active: False,
            UserSession.revoked_at: now,
            UserSession.revoked_reason: "logout",
        },
        synchronize_session=False,
    )
    db.commit()
