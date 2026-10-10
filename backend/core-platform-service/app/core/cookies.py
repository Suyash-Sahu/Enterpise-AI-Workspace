"""
Session cookies, issued and cleared by this service and nowhere else.

Previously the Next.js app minted its own cookies from tokens it fetched over
a server-to-server channel, which meant two places believed they owned the
session. There is now exactly one: the backend sets the cookies on the
responses that create a session and clears them on the response that ends it.

Properties, and why each one:

  httponly    Script cannot read either token, so an XSS cannot lift the
              session out of the page.
  secure      Mandatory in production. Off in development only because the
              dev server is plain http, where a Secure cookie is never sent.
  samesite    lax — sent on top-level GET navigations, withheld from
              cross-site POSTs, iframes and subresource requests, which is
              what keeps CSRF a non-issue for the API. It must not be strict:
              Google sign-in returns via a cross-site-initiated redirect, and
              a Strict cookie is withheld across that whole chain, so the
              session would be stored and then never sent. It is still why
              the Next app proxies /api/v1/* rather than the browser calling
              a different origin directly.
  path        The refresh token is scoped to the auth routes: no other
              endpoint has any reason to receive it, so no other endpoint
              can leak it.
"""

from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from fastapi import Response

from app.core.config import settings

# The refresh cookie is only ever sent to routes under this prefix.
REFRESH_COOKIE_PATH = f"{settings.API_V1_STR}/auth"

# Fallback lifetime for the access cookie when the token carries no expiry.
_DEFAULT_ACCESS_MAX_AGE = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def _refresh_max_age() -> int:
    days = getattr(settings, "REFRESH_TOKEN_EXPIRE_DAYS", 7)
    return int(days) * 24 * 60 * 60


def _access_max_age(expires_at: Optional[datetime]) -> int:
    if expires_at is None:
        return _DEFAULT_ACCESS_MAX_AGE

    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    remaining = int((expires_at - datetime.now(timezone.utc)).total_seconds())

    # A token that is already expired gets a zero-length cookie rather than a
    # negative max-age, which browsers treat inconsistently.
    return max(remaining, 0)


def set_session_cookies(response: Response, tokens: Mapping[str, Any]) -> None:
    """
    Attach a freshly issued token pair to the response.

    `tokens` is the mapping returned by the auth service: access_token,
    refresh_token and an optional expires_at.
    """
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    expires_at = tokens.get("expires_at")

    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at)
        except ValueError:
            expires_at = None

    shared = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.COOKIE_SAMESITE,
    }

    if settings.COOKIE_DOMAIN:
        shared["domain"] = settings.COOKIE_DOMAIN

    response.set_cookie(
        settings.ACCESS_COOKIE_NAME,
        access_token,
        max_age=_access_max_age(expires_at),
        path="/",
        **shared,
    )

    response.set_cookie(
        settings.REFRESH_COOKIE_NAME,
        refresh_token,
        max_age=_refresh_max_age(),
        path=REFRESH_COOKIE_PATH,
        **shared,
    )


def clear_session_cookies(response: Response) -> None:
    """
    Remove both cookies.

    The delete must repeat the path the cookie was set with, or the browser
    treats it as a different cookie and quietly keeps the original.
    """
    shared = {
        "httponly": True,
        "secure": settings.cookie_secure,
        "samesite": settings.COOKIE_SAMESITE,
    }

    if settings.COOKIE_DOMAIN:
        shared["domain"] = settings.COOKIE_DOMAIN

    response.delete_cookie(settings.ACCESS_COOKIE_NAME, path="/", **shared)
    response.delete_cookie(
        settings.REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH, **shared
    )
