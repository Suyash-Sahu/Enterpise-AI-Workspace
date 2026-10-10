"""
Project 9 — P9 Semantic Cache Unit Tests
Tests vector embedding similarity lookup, similarity threshold matching,
cross-workspace security isolation, and data version cache invalidation.
"""

import pytest
from app.cache.semantic_cache import semantic_cache, cosine_similarity
from app.cache.service import cache_service


def test_cosine_similarity_math():
    """Verify cosine similarity calculation."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v3 = [0.0, 1.0, 0.0]
    assert cosine_similarity(v1, v2) == pytest.approx(1.0)
    assert cosine_similarity(v1, v3) == pytest.approx(0.0)


def test_semantic_cache_set_and_hit():
    """Verify semantic cache query storing and lookup above threshold."""
    user_id = "user_sem_1"
    ws_id = "ws_sem_1"
    query_orig = "What is the annual leave allowance for employees?"
    query_similar = "What is the annual leave allowance for employees?"
    payload = {"answer": "Employees receive 20 days of paid annual leave.", "sources": ["leave_policy.pdf"]}

    # Store in semantic cache
    stored = semantic_cache.set(
        query=query_orig,
        value=payload,
        capability="rag_answer",
        user_id=user_id,
        workspace_id=ws_id,
        data_version="v1",
    )
    assert stored is True

    # Retrieve with semantically identical query
    res = semantic_cache.get(
        query=query_similar,
        capability="rag_answer",
        user_id=user_id,
        workspace_id=ws_id,
        data_version="v1",
        threshold=0.90,
    )
    assert res is not None
    cached_payload, score = res
    assert cached_payload == payload
    assert score >= 0.90


def test_semantic_cross_workspace_isolation():
    """
    CRITICAL SECURITY TEST:
    Verifies that Workspace A cached query answer is NEVER returned for Workspace B
    even if the query text and embeddings are 100% identical.
    """
    user_id = "user_security_1"
    ws_a = "ws_security_alpha"
    ws_b = "ws_security_beta"
    query = "What is the confidential quarterly revenue target?"
    payload_a = {"answer": "Workspace Alpha target is $10M."}

    # Store for Workspace Alpha
    semantic_cache.set(
        query=query,
        value=payload_a,
        capability="rag_answer",
        user_id=user_id,
        workspace_id=ws_a,
        data_version="v1",
    )

    # Query Workspace Beta with identical query
    res_b = semantic_cache.get(
        query=query,
        capability="rag_answer",
        user_id=user_id,
        workspace_id=ws_b,
        data_version="v1",
    )
    assert res_b is None, "Cross-workspace security breach: Workspace Beta received Workspace Alpha cached data!"


def test_semantic_data_version_invalidation():
    """Verify that updating workspace data version renders prior semantic cache entries unreachable."""
    user_id = "user_invalidation_1"
    ws_id = "ws_invalidation_1"
    query = "How many sick leave days are permitted?"
    payload_v1 = {"answer": "Employees get 10 sick leave days."}

    # Store under v1
    cache_service.set(
        query=query,
        value=payload_v1,
        capability="rag_answer",
        user_id=user_id,
        workspace_id=ws_id,
    )
    assert cache_service.get(query=query, capability="rag_answer", user_id=user_id, workspace_id=ws_id) == payload_v1

    # Ingest document -> invalidates workspace data version (v1 -> v2)
    cache_service.invalidate_workspace(ws_id)

    # Next query MUST be MISS
    assert cache_service.get(query=query, capability="rag_answer", user_id=user_id, workspace_id=ws_id) is None
