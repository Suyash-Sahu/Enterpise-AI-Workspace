"""
Project 9 — AMOF Cache Package
Exports CacheService, RedisClient, CachePolicyEngine, and health router.
"""

from app.cache.service import cache_service
from app.cache.client import redis_client
from app.cache.policies import cache_policy
from app.cache.vector_index import initialize_vector_index

__all__ = [
    "cache_service",
    "redis_client",
    "cache_policy",
    "initialize_vector_index",
]
