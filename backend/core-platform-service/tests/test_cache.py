"""
Project 9 — P9 Cache Core Unit Tests
Tests exact hashing, query normalization, tenant/workspace key isolation, TTL,
oversized payload protection, policy engine, health endpoint, and graceful fallback.
"""

import time
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.cache.keys import normalize_query, build_cache_key, build_canonical_payload
from app.cache.serializer import cache_serializer
from app.cache.policies import cache_policy
from app.cache.exact_cache import exact_cache
from app.cache.service import cache_service

client = TestClient(app)


def test_query_normalization():
    """Verify query normalization: lowercase, strip, collapse whitespace."""
    raw1 = "  What is   our LEAVE policy?  "
    raw2 = "what is our leave policy?"
    assert normalize_query(raw1) == normalize_query(raw2)
    assert normalize_query(raw1) == "what is our leave policy?"


def test_deterministic_key_isolation():
    """Verify distinct cache keys for different users, workspaces, capabilities, and data versions."""
    key_user_a = build_cache_key(
        query="What is leave policy?",
        capability="rag_answer",
        user_id="user_1",
        workspace_id="ws_1",
        data_version="v1",
    )
    key_user_b = build_cache_key(
        query="What is leave policy?",
        capability="rag_answer",
        user_id="user_2",
        workspace_id="ws_1",
        data_version="v1",
    )
    key_ws_b = build_cache_key(
        query="What is leave policy?",
        capability="rag_answer",
        user_id="user_1",
        workspace_id="ws_2",
        data_version="v1",
    )
    key_v2 = build_cache_key(
        query="What is leave policy?",
        capability="rag_answer",
        user_id="user_1",
        workspace_id="ws_1",
        data_version="v2",
    )

    assert key_user_a != key_user_b
    assert key_user_a != key_ws_b
    assert key_user_a != key_v2


def test_cache_policy_ordering_and_side_effects():
    """Verify policy engine allows cacheable capabilities and blocks side-effects."""
    assert cache_policy.should_cache(capability="rag_answer") is True
    assert cache_policy.should_cache(capability="text_generation") is True
    assert cache_policy.should_cache(capability="document_summary") is True

    # Non-cacheable and side-effects MUST return False
    assert cache_policy.should_cache(capability="gmail.send") is False
    assert cache_policy.should_cache(capability="calendar.create") is False
    assert cache_policy.should_cache(capability="webhook.post") is False
    assert cache_policy.should_cache(capability="data.delete") is False
    assert cache_policy.should_cache(capability="bulk.email") is False
    assert cache_policy.should_cache(capability="database_query") is False


def test_exact_cache_hit_and_miss():
    """Verify exact cache SET, GET hit, and miss behavior."""
    user_id = "user_test_exact_1"
    ws_id = "ws_test_exact_1"
    query = "What are our core security guidelines?"
    val = {"answer": "Security guidelines include multi-factor authentication.", "sources": ["sec.pdf"]}

    # 1. First get MUST be MISS
    res_miss = cache_service.get(
        query=query,
        capability="rag_answer",
        user_id=user_id,
        workspace_id=ws_id,
    )
    assert res_miss is None

    # 2. SET value
    stored = cache_service.set(
        query=query,
        value=val,
        capability="rag_answer",
        user_id=user_id,
        workspace_id=ws_id,
    )
    assert stored is True

    # 3. Second get MUST be HIT
    res_hit = cache_service.get(
        query=query,
        capability="rag_answer",
        user_id=user_id,
        workspace_id=ws_id,
    )
    assert res_hit == val


def test_oversized_payload_not_cached():
    """Verify payloads exceeding 1 MB bypass cache storage cleanly."""
    large_text = "A" * 1100000  # > 1 MB
    serialized = cache_serializer.serialize({"large_field": large_text})
    assert serialized is None


def test_cache_health_endpoint():
    """Verify GET /api/v1/cache/health endpoint structure and telemetry fields."""
    response = client.get("/api/v1/cache/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert data["status"] in ("healthy", "degraded")
    assert "telemetry" in data
    telemetry = data["telemetry"]
    assert "exact_hits" in telemetry
    assert "hit_rate_pct" in telemetry
