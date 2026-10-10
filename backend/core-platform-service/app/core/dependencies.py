from collections.abc import Generator
from typing import Optional

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_token
from app.db.session import SessionLocal
from app.models.user import User

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()


def get_access_token(request: Request) -> Optional[str]:
    """
    Pull the access token from the request.

    The browser sends it as an httpOnly cookie set by this service, and that
    is the path that matters for the app: script never handles the token, so
    an XSS cannot read it out of the page.

    The Authorization header is still accepted for non-browser callers — the
    test suite, scripts and any API client. It is the same token verified the
    same way, not a second identity system: nothing can be authenticated by
    header that could not be authenticated by cookie.
    """
    cookie_token = request.cookies.get(settings.ACCESS_COOKIE_NAME)

    if cookie_token:
        return cookie_token

    authorization = request.headers.get("Authorization", "")
    scheme, _, credentials = authorization.partition(" ")

    if scheme.lower() == "bearer" and credentials.strip():
        return credentials.strip()

    return None


def get_current_user(
    token: Optional[str] = Depends(get_access_token),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise CREDENTIALS_EXCEPTION

    payload = verify_token(token, expected_type="access")

    if payload is None:
        raise CREDENTIALS_EXCEPTION

    # A signed token with a missing or non-numeric subject is a malformed
    # credential, not a server fault — 401, never a 500.
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError):
        raise CREDENTIALS_EXCEPTION

    user = db.query(User).filter(User.id == user_id).first()

    if user is None:
        raise CREDENTIALS_EXCEPTION

    return user
