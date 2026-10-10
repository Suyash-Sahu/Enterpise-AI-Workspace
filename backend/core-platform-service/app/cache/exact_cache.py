"""
Project 9 — Exact Cache Engine
Handles exact SHA-256 key GET/SET/DELETE operations with fallback memory store.
"""

import logging
import time
from typing import Any, Dict, Optional
from app.cache.client import redis_client
from app.cache.serializer import cache_serializer
from app.cache.policies import cache_policy

logger = logging.getLogger(__name__)


class ExactCache:
    """
    Exact hash match cache implementation.
    Uses Redis client when connected; falls back to internal memory cache when disconnected.
    """

    def __init__(self):
        # In-memory fallback cache for degraded / test mode: {key: (value_json, expire_at)}
        self._memory_cache: Dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> Optional[Any]:
        """
        Retrieves cached result for key if unexpired.
        Returns deserialized payload object or None on miss.
        """
        # Try Redis first
        if redis_client.is_connected:
            raw_json = redis_client.get(key)
            if raw_json:
                return cache_serializer.deserialize(raw_json)
            return None

        # Fallback in-memory store
        self._cleanup_memory()
        item = self._memory_cache.get(key)
        if item:
            val_json, expire_at = item
            if time.time() < expire_at:
                return cache_serializer.deserialize(val_json)
            else:
                del self._memory_cache[key]
        return None

    def set(self, key: str, value: Any, capability: str, ttl_seconds: Optional[int] = None) -> bool:
        """
        Stores payload in exact cache with capability TTL.
        """
        ttl = ttl_seconds or cache_policy.get_capability_ttl(capability)
        json_str = cache_serializer.serialize(value)
        if not json_str:
            # Oversized or un-serializable payload
            return False

        if redis_client.is_connected:
            return redis_client.set(key, json_str, ttl_seconds=ttl)

        # Fallback memory store
        expire_at = time.time() + ttl
        self._memory_cache[key] = (json_str, expire_at)
        return True

    def delete(self, key: str) -> bool:
        """Deletes key from cache."""
        if redis_client.is_connected:
            redis_client.delete(key)
        if key in self._memory_cache:
            del self._memory_cache[key]
        return True

    def _cleanup_memory(self) -> None:
        """Purge expired items from in-memory fallback store."""
        now = time.time()
        expired = [k for k, (_, exp) in self._memory_cache.items() if now >= exp]
        for k in expired:
            del self._memory_cache[k]


exact_cache = ExactCache()
