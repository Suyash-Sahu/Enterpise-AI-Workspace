"""
Project 9 — Cache Policy Engine
Determines which operations are cacheable and assigns capability TTLs.
Enforces P8 Side-Effect Safety Invariant: side-effect actions bypass cache lookup entirely.
"""

from typing import Optional, Set
from app.core.config import settings

CACHEABLE_CAPABILITIES: Set[str] = {
    "rag_search",
    "rag_answer",
    "text_generation",
    "document_summary",
}

NON_CACHEABLE_ACTIONS: Set[str] = {
    "gmail.send",
    "calendar.create",
    "calendar.update",
    "webhook.post",
    "data.delete",
    "bulk.email",
    "database_query",  # Disabled initially per P9 spec until dynamic DB versioning
}

SIDE_EFFECT_SUFFIXES = (".send", ".create", ".update", ".delete", ".post", ".put", ".remove")


class CachePolicyEngine:
    """
    Evaluates cacheability policy prior to performing any cache GET or SET.
    """

    @staticmethod
    def should_cache(capability: str, action_type: Optional[str] = None) -> bool:
        """
        Determines whether a given capability or action is eligible for caching.

        Security Ordering Invariant:
        Side-effect actions and P8 approval workflows MUST return False and bypass
        cache operations completely.
        """
        if not settings.CACHE_ENABLED:
            return False

        # 1. Check explicit action_type
        if action_type:
            action_lower = action_type.lower()
            if action_lower in NON_CACHEABLE_ACTIONS:
                return False
            if any(action_lower.endswith(sfx) for sfx in SIDE_EFFECT_SUFFIXES):
                return False

        # 2. Check capability
        cap_lower = capability.lower()
        if cap_lower in NON_CACHEABLE_ACTIONS:
            return False
        if any(cap_lower.endswith(sfx) for sfx in SIDE_EFFECT_SUFFIXES):
            return False

        # 3. Must be in explicitly allowlisted cacheable capabilities
        return cap_lower in CACHEABLE_CAPABILITIES

    @staticmethod
    def get_capability_ttl(capability: str) -> int:
        """Returns Redis TTL in seconds based on capability policy."""
        cap_lower = capability.lower()
        if "rag" in cap_lower:
            return settings.CACHE_RAG_TTL_SECONDS
        if "generation" in cap_lower or "summary" in cap_lower:
            return settings.CACHE_GENERATION_TTL_SECONDS
        return settings.CACHE_DEFAULT_TTL_SECONDS


cache_policy = CachePolicyEngine()
