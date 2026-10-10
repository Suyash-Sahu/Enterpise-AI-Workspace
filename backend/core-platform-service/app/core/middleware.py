"""Security response headers, and origin enforcement for cookie auth."""

from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from app.core.config import settings

# One year, which is the minimum for HSTS preload eligibility.
HSTS_MAX_AGE = 31_536_000


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Adds the headers a JSON API should always send.

    The CSP is deliberately restrictive because this service returns JSON, not
    pages — the only HTML it serves is the Swagger UI, which is excluded so its
    bundled assets keep working.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self.is_production = settings.ENVIRONMENT.lower() in ("production", "prod")

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # Never let a browser or proxy cache an API response: they carry
        # per-user data and, on the auth routes, credentials.
        if request.url.path.startswith(settings.API_V1_STR):
            response.headers["Cache-Control"] = "no-store"

        if not request.url.path.startswith(("/docs", "/redoc", "/openapi.json")):
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"
            )

        # HSTS only over TLS: sending it on plain HTTP does nothing, and
        # sending it in local development can pin localhost to https.
        if self.is_production:
            response.headers["Strict-Transport-Security"] = (
                f"max-age={HSTS_MAX_AGE}; includeSubDomains"
            )

        return response


# Methods that cannot change state, so a cross-site request carrying them is
# not a CSRF concern.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """
    Reject state-changing requests that declare a foreign origin.

    Sessions are carried by SameSite=strict cookies, which the browser already
    refuses to attach to a cross-site request — that is the primary defence
    and it is what makes a CSRF token unnecessary here. This is the second
    layer, for the cases SameSite alone does not settle: a cookie policy
    loosened later, a browser that does not honour it, or a same-site but
    untrusted subdomain.

    Requests with no Origin and no Referer are allowed through: they are not
    browser-initiated, so they carry no ambient cookie to abuse. A caller that
    presents a bearer token instead of a cookie is likewise unaffected, since
    a cross-site page cannot read a token it was never given.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)
        self._allowed = {
            self._origin_of(origin) for origin in settings.cors_origins
        }

    @staticmethod
    def _origin_of(value: str) -> str:
        parsed = urlparse(value)

        if not parsed.scheme or not parsed.netloc:
            return value.rstrip("/")

        return f"{parsed.scheme}://{parsed.netloc}"

    async def dispatch(self, request: Request, call_next):
        if request.method.upper() in SAFE_METHODS:
            return await call_next(request)

        # Only a cookie-authenticated request carries ambient authority.
        if settings.ACCESS_COOKIE_NAME not in request.cookies and (
            settings.REFRESH_COOKIE_NAME not in request.cookies
        ):
            return await call_next(request)

        stated = request.headers.get("origin") or request.headers.get("referer")

        if stated and self._origin_of(stated) not in self._allowed:
            return JSONResponse(
                status_code=403,
                content={"detail": "Cross-origin request rejected"},
            )

        return await call_next(request)
