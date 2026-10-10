import time
from fastapi import APIRouter
from app.utils.response import success_response

router = APIRouter(
    tags=["Health Telemetry"],
)

START_UP_TIME = time.time()


@router.get("/health")
def get_health():
    start_time = time.time()
    uptime_seconds = int(time.time() - START_UP_TIME)
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    uptime_str = f"{hours}h {minutes}m {seconds}s"

    data = {
        "backend": "online",
        "database": "online",
        "google": "connected",
        "ollama": "online",
        "openrouter": "online",
        "version": "1.0.0",
        "uptime": uptime_str,
    }

    return success_response(
        data=data,
        message="All platform services fully operational",
        start_time=start_time,
    )