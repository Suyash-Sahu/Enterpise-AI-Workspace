"""
Application-wide error handling.

Clients get a stable shape and a generic message; the detail goes to the log
with a correlation id so an operator can find it. Previously unhandled errors
fell through to FastAPI's default handler, and a dozen routes returned
`str(exception)` directly, leaking driver errors, SQL fragments and paths.
"""

import logging
import uuid

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings

logger = logging.getLogger(__name__)


def _is_production() -> bool:
    return settings.ENVIRONMENT.lower() in ("production", "prod")


def _error_body(message: str, correlation_id: str) -> dict:
    return {"detail": message, "correlation_id": correlation_id}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        # HTTPException detail is written by us and safe to return as-is.
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        # Field-level errors are useful to the caller and describe only what
        # they sent, but the raw input is echoed back by default — drop it, it
        # can contain the password that failed validation.
        errors = [
            {
                "field": ".".join(str(p) for p in err.get("loc", [])[1:]),
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", ""),
            }
            for err in exc.errors()
        ]

        return JSONResponse(
            # 422; the ENTITY spelling is deprecated in this Starlette.
            status_code=422,
            content={"detail": "Request validation failed", "errors": errors},
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_exception_handler(
        request: Request,
        exc: SQLAlchemyError,
    ) -> JSONResponse:
        correlation_id = str(uuid.uuid4())
        logger.error(
            "Database error [%s] on %s %s",
            correlation_id,
            request.method,
            request.url.path,
            exc_info=exc,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("A database error occurred.", correlation_id),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        correlation_id = str(uuid.uuid4())
        logger.error(
            "Unhandled error [%s] on %s %s",
            correlation_id,
            request.method,
            request.url.path,
            exc_info=exc,
        )

        message = "An internal error occurred."

        # Outside production, name the exception type to keep debugging sane —
        # still never the message, which is where user data tends to end up.
        if not _is_production():
            message = f"{message} ({type(exc).__name__})"

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body(message, correlation_id),
        )
