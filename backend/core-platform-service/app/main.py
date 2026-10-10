from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.logging_config import configure_logging
from app.core.errors import register_exception_handlers
from app.core.middleware import CsrfOriginMiddleware, SecurityHeadersMiddleware
from app.core.rate_limit import limiter, rate_limit_handler
configure_logging()

# Aliased: a bare `import app.models` binds the name `app` to the package,
# which is then shadowed by the FastAPI instance created below.
import app.models as _models  # noqa: F401 — registers ORM models on Base.metadata

# Schema is owned by Alembic; run `alembic upgrade head` to create or update it.
# The previous `Base.metadata.create_all(...)` here was a no-op anyway: it ran
# against a second, empty declarative base. Now that the two bases are unified
# it would actually create tables, which would collide with Alembic's version
# tracking — so it is removed rather than fixed.

from app.api.router import api_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Enterprise AI Workspace — Shared Backend Architecture serving all 12 project modules.",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)
register_exception_handlers(app)

# Middleware runs in reverse registration order, so this block reads
# bottom-up: session -> rate limit -> CORS -> security headers.
app.add_middleware(SecurityHeadersMiddleware)

# Cookie sessions are SameSite=strict; this rejects a state-changing request
# that claims a foreign origin even so.
app.add_middleware(CsrfOriginMiddleware)

# CORS is restricted to the configured frontend origins. A wildcard here is not
# just permissive, it is invalid: browsers reject "*" whenever credentials are
# allowed, so the previous config was both insecure in intent and broken.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
    max_age=600,
)

# Applies RATE_LIMIT_DEFAULT to every route; tighter per-route limits are
# declared with @limiter.limit on the routes themselves.
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
    https_only=settings.ENVIRONMENT.lower() in ("production", "prod"),
    same_site="lax",
)

# Central Versioned Router /api/v1
app.include_router(api_router)


@app.get("/")
def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "status": "online",
        "api_v1": "/api/v1",
        "docs": "/docs",
    }
