"""
Project 9 — System Flow & P8 Approval Protection Integration Tests
Tests full P7 -> P5 -> P9 -> P3/P6 execution pipeline and enforces P8 side-effect bypass protection.
"""

import pytest
from app.db.session import SessionLocal
from app.schemas.execution import ExecutionRequest, ExecutionStatus
from app.services.execution_manager import execution_manager
from app.cache.service import cache_service
from app.cache.policies import cache_policy


_redis = None


def _redis_available() -> bool:
    """True when a real Redis is reachable.

    The caching assertions below require one: without it the cache
    layer runs in degraded mode and correctly serves nothing, so the
    test would be asserting against a disabled feature.
    """
    from app.cache.client import redis_client
    return bool(getattr(redis_client, "is_connected", False))


pytestmark = pytest.mark.skipif(
    not _redis_available(),
    reason="requires a reachable Redis (set REDIS_URL and CACHE_ENABLED=true)",
)



def test_p7_p5_p9_execution_pipeline_caching():
    """Verify P5 Execution Manager transparent caching flow for cacheable capabilities."""
    db = SessionLocal()
    user_id = "user_pipeline_test_1"
    ws_id = f"ws_user_{user_id}"
    query = "Summarize the project 9 caching architecture."
    req = ExecutionRequest(
        task_type="rag_search",
        input={"query": query, "top_k": 3, "workspace_id": ws_id},
        execution_mode="auto",
    )

    try:
        # 1. First execution -> CACHE MISS -> Execute
        res1 = execution_manager.execute(db=db, request=req, owner_id=user_id)
        assert res1.status == ExecutionStatus.COMPLETED
        assert res1.execution_id is not None
        assert res1.provider != "amof_cache"

        # 2. Second execution with identical input -> CACHE HIT -> Instant cache return
        res2 = execution_manager.execute(db=db, request=req, owner_id=user_id)
        assert res2.status == ExecutionStatus.COMPLETED
        assert res2.provider == "amof_cache"
        assert res2.model == "cache_v1"
    finally:
        db.close()


def test_cache_cannot_bypass_approval():
    """
    CRITICAL P8 INTEGRATION TEST:
    Verifies that side-effect operations (gmail.send, calendar.create, webhook.post, data.delete, bulk.email)
    are strictly NON-CACHEABLE and ALWAYS bypass cache lookup to enforce P8 Human-in-the-Loop approvals.
    """
    non_cacheable_actions = [
        "gmail.send",
        "calendar.create",
        "calendar.update",
        "webhook.post",
        "data.delete",
        "bulk.email",
    ]

    for action in non_cacheable_actions:
        # Policy engine check MUST be False
        assert cache_policy.should_cache(capability=action, action_type=action) is False

        # Cache get MUST return None
        res_get = cache_service.get(
            query="Send email notice to team",
            capability=action,
            user_id="user_p8_security",
            workspace_id="ws_user_p8_security",
            action_type=action,
        )
        assert res_get is None, f"Security breach: Cache returned hit for non-cacheable P8 side-effect '{action}'"

        # Cache set MUST return False
        res_set = cache_service.set(
            query="Send email notice to team",
            value={"status": "sent"},
            capability=action,
            user_id="user_p8_security",
            workspace_id="ws_user_p8_security",
            action_type=action,
        )
        assert res_set is False, f"Security breach: Cache stored entry for non-cacheable P8 side-effect '{action}'"
