import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

import bcrypt
from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)
from jose import JWTError, jwt

from app.core.config import settings

# argon2id with the argon2-cffi defaults (RFC 9106 low-memory profile).
# passlib was removed: 1.7.4 reads bcrypt.__about__, deleted in bcrypt 4.1, so
# the pinned dependency set could not hash a password at all.
_argon2 = PasswordHasher()

TokenType = Literal["access", "refresh"]

# bcrypt truncates past 72 bytes. argon2 has no such limit, but the cap is kept
# so a password that worked before cannot silently change meaning.
MAX_PASSWORD_BYTES = 72

# A real argon2 hash of the literal "timing-equalisation", used only to spend a
# comparable amount of time on the login path where no user was found.
_TIMING_EQUALISATION_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$"
    "yE0bThyTTkx10niDJLRehw$R4Z9gLb89WK3Foh6Hs25S/DtDSXBdDSfWj55wUL85/E"
)


def _is_bcrypt_hash(hashed: str) -> bool:
    return hashed.startswith(("$2a$", "$2b$", "$2x$", "$2y$"))


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise ValueError(
            f"Password must be at most {MAX_PASSWORD_BYTES} bytes"
        )

    return _argon2.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """
    Verify against argon2 or a legacy bcrypt hash.

    Both backends compare in constant time. Any malformed or unrecognised hash
    is a non-match rather than an exception, so a corrupt row cannot turn a
    failed login into a 500.
    """
    if not hashed_password:
        return False

    try:
        if _is_bcrypt_hash(hashed_password):
            return bcrypt.checkpw(
                plain_password.encode("utf-8")[:MAX_PASSWORD_BYTES],
                hashed_password.encode("utf-8"),
            )

        return _argon2.verify(hashed_password, plain_password)

    except (
        VerifyMismatchError,
        VerificationError,
        InvalidHashError,
        ValueError,
        TypeError,
    ):
        return False


def needs_rehash(hashed_password: str) -> bool:
    """
    True when a verified hash should be replaced.

    Covers legacy bcrypt hashes and argon2 hashes made with older parameters,
    so stored credentials upgrade themselves as users log in.
    """
    if _is_bcrypt_hash(hashed_password):
        return True

    try:
        return _argon2.check_needs_rehash(hashed_password)
    except (InvalidHashError, ValueError, TypeError):
        return False


def dummy_verify() -> None:
    """
    Burn roughly one verification's worth of time.

    Called on the "user does not exist" login path so that a missing account
    and a wrong password take the same wall-clock time and cannot be told apart
    by timing.
    """
    verify_password("timing-equalisation", _TIMING_EQUALISATION_HASH)


def _signing_key(token_type: TokenType) -> str:
    return (
        settings.REFRESH_SECRET_KEY
        if token_type == "refresh"
        else settings.SECRET_KEY
    )


def _create_token(
    data: dict,
    token_type: TokenType,
    expires_delta: timedelta,
) -> tuple[str, str, datetime]:
    """
    Returns (encoded_token, jti, expires_at).

    The jti is what makes a token individually revocable: it is stored
    server-side and checked on every use.
    """
    now = datetime.now(timezone.utc)
    expires_at = now + expires_delta
    jti = str(uuid.uuid4())

    to_encode = data.copy()
    to_encode.update(
        {
            "exp": expires_at,
            "iat": now,
            "nbf": now,
            "jti": jti,
            "typ": token_type,
        }
    )

    encoded = jwt.encode(
        to_encode,
        _signing_key(token_type),
        algorithm=settings.ALGORITHM,
    )

    return encoded, jti, expires_at


def create_access_token(data: dict) -> tuple[str, str, datetime]:
    return _create_token(
        data,
        "access",
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(data: dict) -> tuple[str, str, datetime]:
    return _create_token(
        data,
        "refresh",
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def verify_token(
    token: str,
    expected_type: TokenType,
) -> Optional[dict[str, Any]]:
    """
    Decode and validate a token, returning its claims or None.

    `expected_type` is required rather than optional: a caller that forgets to
    state which kind of token it wants is a bug, not a permissive default.
    """
    try:
        payload = jwt.decode(
            token,
            _signing_key(expected_type),
            algorithms=[settings.ALGORITHM],
        )
    except JWTError:
        return None

    if payload.get("typ") != expected_type:
        return None

    if not payload.get("sub") or not payload.get("jti"):
        return None

    return payload


def hash_token(token: str) -> str:
    """
    Refresh tokens are stored as SHA-256 digests, so a database dump does not
    hand over usable credentials. Digest (not bcrypt) because lookup happens on
    every refresh and the input already has full entropy.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_token_family_id() -> str:
    return secrets.token_urlsafe(24)
