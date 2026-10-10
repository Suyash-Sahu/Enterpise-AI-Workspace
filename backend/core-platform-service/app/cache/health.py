"""
Project 9 — Cache Operational Health Endpoint
Provides GET /api/v1/cache/health for cache verification and telemetry stats.
Does not expose sensitive credentials in response payloads.
"""

from fastapi import APIRouter
from app.cache.client import redis_client
from app.cache.service import cache_service
from app.core.config import settings

router = APIRouter(prefix="/cache", tags=["cache"])


@router.get("/health")
def get_cache_health():
    """
    Returns operational health status and telemetry stats for P9 Caching Layer.
    """
    connected = redis_client.is_connected
    status_str = "healthy" if (settings.CACHE_ENABLED and connected) else "degraded"

    return {
        "status": status_str,
        "cache_enabled": settings.CACHE_ENABLED,
        "semantic_enabled": settings.CACHE_SEMANTIC_ENABLED,
        "redis": {
            "connected": connected,
            "namespace": settings.CACHE_NAMESPACE,
            "schema_version": settings.CACHE_SCHEMA_VERSION,
        },
        "telemetry": cache_service.get_telemetry(),
    }
