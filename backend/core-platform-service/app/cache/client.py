"""
Project 9 — Redis Client & Connection Manager
Thread-safe Redis client wrapper with connection pooling, graceful fallback,
and exception handling for operational resilience.
"""

import logging
from typing import Optional
import redis
from app.core.config import settings

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Manages Redis connection pool and provides resilient key-value operations.
    Falls back gracefully when Redis server is unreachable.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or settings.REDIS_URL
        self._redis_client: Optional[redis.Redis] = None
        self._is_connected: bool = False
        self._connect()

    def _connect(self) -> None:
        """Initialize Redis connection pool."""
        try:
            self._redis_client = redis.Redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_timeout=2.0,
                socket_connect_timeout=2.0,
            )
            # Test ping
            self._redis_client.ping()
            self._is_connected = True
            logger.info(f"[RedisClient] Connected to Redis at {self.redis_url}")
        except Exception as e:
            self._is_connected = False
            self._redis_client = None
            logger.warning(f"[RedisClient] Redis connection unavailable ({e}). Operating in degraded mode.")

    @property
    def is_connected(self) -> bool:
        """Check if Redis connection is active."""
        if not self._redis_client:
            return False
        try:
            self._redis_client.ping()
            self._is_connected = True
            return True
        except Exception:
            self._is_connected = False
            return False

    def get(self, key: str) -> Optional[str]:
        """Get string value from Redis."""
        if not self.is_connected or not self._redis_client:
            return None
        try:
            return self._redis_client.get(key)
        except Exception as e:
            logger.warning(f"[RedisClient] GET failed for key={key}: {e}")
            return None

    def set(self, key: str, value: str, ttl_seconds: Optional[int] = None) -> bool:
        """Set string value in Redis with optional TTL."""
        if not self.is_connected or not self._redis_client:
            return False
        try:
            if ttl_seconds:
                return bool(self._redis_client.setex(key, ttl_seconds, value))
            return bool(self._redis_client.set(key, value))
        except Exception as e:
            logger.warning(f"[RedisClient] SET failed for key={key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        """Delete key from Redis."""
        if not self.is_connected or not self._redis_client:
            return False
        try:
            return bool(self._redis_client.delete(key))
        except Exception as e:
            logger.warning(f"[RedisClient] DELETE failed for key={key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        if not self.is_connected or not self._redis_client:
            return False
        try:
            return bool(self._redis_client.exists(key))
        except Exception as e:
            logger.warning(f"[RedisClient] EXISTS failed for key={key}: {e}")
            return False

    def ping(self) -> bool:
        """Ping Redis server."""
        return self.is_connected

    def get_raw_client(self) -> Optional[redis.Redis]:
        """Access underlying redis-py client instance for advanced commands (e.g. FT.SEARCH)."""
        if self.is_connected:
            return self._redis_client
        return None


redis_client = RedisClient()
