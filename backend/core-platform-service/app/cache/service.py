"""
Project 9 — Unified AMOF Cache Service
Main interface for exact & semantic cache operations, workspace data versioning,
policy enforcement, hit/miss telemetry tracking, and P8 side-effect protection.
"""

import logging
from typing import Any, Dict, Optional
from app.cache.exact_cache import exact_cache
from app.cache.semantic_cache import semantic_cache
from app.cache.policies import cache_policy
from app.cache.keys import build_cache_key

logger = logging.getLogger(__name__)


class CacheService:
    """
    Unified AMOF Cache Service providing transparent exact and semantic caching.
    """

    def __init__(self):
        # Telemetry counters
        self.exact_hits: int = 0
        self.semantic_hits: int = 0
        self.cache_misses: int = 0
        self.cache_sets: int = 0
        self.cache_invalidations: int = 0
        self.redis_errors: int = 0

        # Workspace data version registry: workspace_id -> version_number
        self._workspace_versions: Dict[str, int] = {}

    def get_workspace_data_version(self, workspace_id: str) -> str:
        """Returns version string v1, v2, ... for workspace."""
        ver = self._workspace_versions.get(str(workspace_id), 1)
        return f"v{ver}"

    def invalidate_workspace(self, workspace_id: str) -> None:
        """
        Increments workspace data version number so old cache entries become unreachable.
        """
        current = self._workspace_versions.get(str(workspace_id), 1)
        self._workspace_versions[str(workspace_id)] = current + 1
        self.cache_invalidations += 1
        logger.info(
            f"[CacheService] Workspace '{workspace_id}' invalidated. "
            f"Data version updated from v{current} to v{current + 1}."
        )

    def get(
        self,
        query: str,
        capability: str,
        user_id: str,
        workspace_id: str,
        action_type: Optional[str] = None,
        model: str = "qwen2.5:7b",
        system_prompt_version: str = "v1",
        temperature: float = 0.2,
        additional_params: Optional[Dict[str, Any]] = None,
    ) -> Optional[Any]:
        """
        Unified cache retrieval interface.

        Policy Ordering Rule:
        Evaluates cacheability policy BEFORE checking cache. Side-effects and P8 approval
        actions return None immediately.
        """
        if not cache_policy.should_cache(capability=capability, action_type=action_type):
            return None

        data_version = self.get_workspace_data_version(workspace_id)

        # 1. Exact Cache Lookup
        cache_key = build_cache_key(
            query=query,
            capability=capability,
            user_id=user_id,
            workspace_id=workspace_id,
            data_version=data_version,
            model=model,
            system_prompt_version=system_prompt_version,
            temperature=temperature,
            additional_params=additional_params,
        )

        exact_res = exact_cache.get(cache_key)
        if exact_res is not None:
            self.exact_hits += 1
            logger.info(f"[CacheService] Exact Cache HIT for capability='{capability}' key='{cache_key}'")
            return exact_res

        # 2. Semantic Vector Cache Lookup
        sem_res = semantic_cache.get(
            query=query,
            capability=capability,
            user_id=user_id,
            workspace_id=workspace_id,
            data_version=data_version,
            model_config=model,
        )
        if sem_res is not None:
            payload, sim_score = sem_res
            self.semantic_hits += 1
            logger.info(
                f"[CacheService] Semantic Cache HIT (similarity={sim_score:.4f}) for capability='{capability}'"
            )
            return payload

        self.cache_misses += 1
        return None

    def set(
        self,
        query: str,
        value: Any,
        capability: str,
        user_id: str,
        workspace_id: str,
        action_type: Optional[str] = None,
        model: str = "qwen2.5:7b",
        system_prompt_version: str = "v1",
        temperature: float = 0.2,
        additional_params: Optional[Dict[str, Any]] = None,
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Unified cache storage interface for exact and semantic caches.
        """
        if not cache_policy.should_cache(capability=capability, action_type=action_type):
            return False

        data_version = self.get_workspace_data_version(workspace_id)
        cache_key = build_cache_key(
            query=query,
            capability=capability,
            user_id=user_id,
            workspace_id=workspace_id,
            data_version=data_version,
            model=model,
            system_prompt_version=system_prompt_version,
            temperature=temperature,
            additional_params=additional_params,
        )

        # 1. Set Exact Cache
        exact_ok = exact_cache.set(key=cache_key, value=value, capability=capability, ttl_seconds=ttl_seconds)

        # 2. Set Semantic Cache
        sem_ok = semantic_cache.set(
            query=query,
            value=value,
            capability=capability,
            user_id=user_id,
            workspace_id=workspace_id,
            data_version=data_version,
            model_config=model,
            ttl_seconds=ttl_seconds,
        )

        if exact_ok or sem_ok:
            self.cache_sets += 1
            return True
        return False

    def get_telemetry(self) -> Dict[str, Any]:
        """Returns hit/miss counters and calculated hit rate percentage."""
        total_requests = self.exact_hits + self.semantic_hits + self.cache_misses
        hit_rate = ((self.exact_hits + self.semantic_hits) / total_requests * 100.0) if total_requests > 0 else 0.0

        return {
            "exact_hits": self.exact_hits,
            "semantic_hits": self.semantic_hits,
            "cache_misses": self.cache_misses,
            "cache_sets": self.cache_sets,
            "cache_invalidations": self.cache_invalidations,
            "redis_errors": self.redis_errors,
            "hit_rate_pct": round(hit_rate, 1),
        }


cache_service = CacheService()
