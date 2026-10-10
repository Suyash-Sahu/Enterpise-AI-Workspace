"""
Request rate limiting.

Backed by slowapi. In-process storage by default; set RATE_LIMIT_STORAGE_URI to
a redis:// URL to share counters across workers, which you need as soon as more
than one uvicorn worker is running.
"""

import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)


# Peers we accept X-Forwarded-For from. The API binds loopback and is reached
# through the Next proxy, so the only legitimate source of that header is the
# proxy itself; anything else could spoof its way into a private bucket.
TRUSTED_PROXY_PEERS = frozenset({"127.0.0.1", "::1", "localhost"})


def _subject_from_jwt(token: str) -> str | None:
    """
    The `sub` claim, read without verification.

    Unverified on purpose: this only buckets requests, it grants nothing, and
    forging a subject throttles the forged subject rather than escaping the
    limit.
    """
    parts = token.split(".")

    if len(parts) != 3:
        return None

    import base64
    import json

    try:
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None

    sub = claims.get("sub")
    return str(sub) if sub else None


def _peer_address(request: Request) -> str:
    """
    The caller's address, seen through the proxy.

    Every browser request now arrives via the Next rewrite, so the peer is
    always the proxy — without this, all users share one bucket and any one of
    them can exhaust the limit for everyone.
    """
    peer = get_remote_address(request) or "unknown"

    if peer in TRUSTED_PROXY_PEERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            # Left-most entry is the original client.
            original = forwarded.split(",")[0].strip()
            if original:
                return original

    return peer


def client_key(request: Request) -> str:
    """
    Identify the caller for limiting purposes.

    Prefers the authenticated subject so one user on a shared address cannot
    spend everyone else's budget. The browser authenticates with a cookie, so
    that is checked as well as the Authorization header — checking only the
    header meant every cookie-authenticated user fell through to the peer
    address, which behind the proxy is the same address for all of them.
    """
    auth = request.headers.get("authorization", "")

    if auth.lower().startswith("bearer "):
        subject = _subject_from_jwt(auth[7:])
        if subject:
            return f"user:{subject}"

    cookie_token = request.cookies.get(settings.ACCESS_COOKIE_NAME)

    if cookie_token:
        subject = _subject_from_jwt(cookie_token)
        if subject:
            return f"user:{subject}"

    # Refresh and login carry no access token by definition, so they bucket by
    # address. The refresh cookie is a stable per-session value, which is a
    # tighter bucket than the address when one is present.
    refresh_token = request.cookies.get(settings.REFRESH_COOKIE_NAME)

    if refresh_token:
        subject = _subject_from_jwt(refresh_token)
        if subject:
            return f"session:{subject}"

    return f"ip:{_peer_address(request)}"


limiter = Limiter(
    key_func=client_key,
    storage_uri=settings.RATE_LIMIT_STORAGE_URI or None,
    enabled=settings.RATE_LIMIT_ENABLED,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)


def rate_limit_handler(
    request: Request,
    exc: RateLimitExceeded,
) -> JSONResponse:
    logger.warning(
        "Rate limit exceeded: key=%s path=%s limit=%s",
        client_key(request),
        request.url.path,
        exc.detail,
    )

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": "Too many requests. Please slow down and try again shortly."
        },
        headers={"Retry-After": "60"},
    )
