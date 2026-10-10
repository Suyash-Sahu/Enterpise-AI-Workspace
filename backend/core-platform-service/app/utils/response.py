import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


def success_response(
    data: Any = None,
    message: str = "Success",
    start_time: Optional[float] = None,
    status_code: int = 200,
) -> dict:
    execution_time = (
        round(time.time() - start_time, 3)
        if start_time
        else 0.0
    )
    return {
        "success": True,
        "data": data if data is not None else {},
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_time": execution_time,
    }


def error_response(
    message: str = "An error occurred",
    data: Any = None,
    start_time: Optional[float] = None,
    # 500 is the honest default: every remaining caller is an `except`
    # catch-all. Client-error cases pass 400/403/404 explicitly.
    status_code: int = 500,
    exc: Optional[BaseException] = None,
) -> JSONResponse:
    """
    Build an error response.

    Returns a JSONResponse carrying `status_code`. It previously returned a
    plain dict, so every failure reached the client as HTTP 200 with
    `success: false` in the body — including 403s — and proxies, monitoring and
    retry logic all saw a success.

    Pass `exc` rather than interpolating the exception into `message`: the
    detail is logged against a correlation id the caller can quote, and never
    returned.
    """
    execution_time = (
        round(time.time() - start_time, 3)
        if start_time
        else 0.0
    )

    body = {
        "success": False,
        "data": data,
        "message": message,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "execution_time": execution_time,
    }

    if exc is not None:
        correlation_id = str(uuid.uuid4())
        logger.error(
            "Handled error [%s]: %s", correlation_id, message, exc_info=exc
        )
        body["correlation_id"] = correlation_id

    # `detail` mirrors `message` so clients reading FastAPI's standard error
    # shape and clients reading this envelope both find the reason.
    body["detail"] = message

    return JSONResponse(
        status_code=status_code,
        content=jsonable_encoder(body),
    )
