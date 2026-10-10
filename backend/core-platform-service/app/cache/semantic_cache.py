"""
Project 9 — Semantic Vector Cache Engine
Reuses P3 EmbeddingService for vector generation.
Performs TAG-filtered vector similarity search with cosine distance conversion,
strict multi-tenant data version isolation, and Redis capability TTL.
"""

import logging
import math
import struct
import time
from typing import Any, Dict, List, Optional, Tuple

from app.cache.client import redis_client
from app.cache.serializer import cache_serializer
from app.cache.policies import cache_policy
from app.core.config import settings
from app.rag.embeddings import embedding_service

logger = logging.getLogger(__name__)

INDEX_NAME = "idx:semantic_cache"


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Computes cosine similarity between two vector lists."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class SemanticCache:
    """
    Semantic Cache providing vector similarity search using Redis Stack or in-memory fallback.
    """

    def __init__(self):
        # In-memory vector store fallback: key -> dict metadata
        self._memory_store: Dict[str, Dict[str, Any]] = {}

    def get(
        self,
        query: str,
        capability: str,
        user_id: str,
        workspace_id: str,
        data_version: str = "v1",
        model_config: str = "qwen2.5:7b",
        threshold: Optional[float] = None,
    ) -> Optional[Tuple[Any, float]]:
        """
        Searches for a semantically similar cached query result.
        Returns (result_payload, similarity_score) if similarity >= threshold (default 0.90),
        or None on miss.
        """
        if not settings.CACHE_SEMANTIC_ENABLED or not query:
            return None

        sim_threshold = threshold or settings.CACHE_SEMANTIC_THRESHOLD

        # 1. Generate query embedding vector
        try:
            query_vec = embedding_service.generate_embedding(query)
        except Exception as e:
            logger.warning(f"[SemanticCache] Embedding generation error: {e}")
            return None

        # 2. Redis FT.SEARCH query execution
        if redis_client.is_connected:
            raw_client = redis_client.get_raw_client()
            if raw_client:
                try:
                    # Construct strict TAG filter query
                    filter_str = (
                        f"(@user_id:{{{user_id}}} @workspace_id:{{{workspace_id}}} "
                        f"@capability:{{{capability}}} @model_config:{{{model_config}}} "
                        f"@data_version:{{{data_version}}})"
                    )
                    query_cmd = f"{filter_str}=>[KNN 5 @vector $vec AS score]"
                    vec_bytes = struct.pack(f"{len(query_vec)}f", *query_vec)

                    res = raw_client.execute_command(
                        "FT.SEARCH",
                        INDEX_NAME,
                        query_cmd,
                        "PARAMS",
                        "2",
                        "vec",
                        vec_bytes,
                        "SORTBY",
                        "score",
                        "ASC",
                        "RETURN",
                        "3",
                        "cache_key",
                        "result_json",
                        "score",
                        "DIALECT",
                        "2",
                    )

                    # Parse Redis FT.SEARCH response
                    # Format: [total_count, doc_id_1, [field_1, val_1, ...], ...]
                    if res and isinstance(res, list) and res[0] > 0:
                        doc_fields = res[2]
                        field_dict = {}
                        for i in range(0, len(doc_fields), 2):
                            k = doc_fields[i].decode("utf-8") if isinstance(doc_fields[i], bytes) else str(doc_fields[i])
                            v = doc_fields[i + 1].decode("utf-8") if isinstance(doc_fields[i + 1], bytes) else str(doc_fields[i + 1])
                            field_dict[k] = v

                        dist = float(field_dict.get("score", 1.0))
                        similarity = max(0.0, 1.0 - dist)
                        result_json = field_dict.get("result_json")

                        if similarity >= sim_threshold and result_json:
                            payload = cache_serializer.deserialize(result_json)
                            if payload is not None:
                                logger.info(
                                    f"[SemanticCache] HIT (score={similarity:.4f} >= {sim_threshold}) "
                                    f"for query='{query[:30]}...'"
                                )
                                return payload, similarity
                except Exception as ex:
                    logger.debug(f"[SemanticCache] Redis FT.SEARCH query fallback: {ex}")

        # 3. Fallback In-Memory Vector Search
        return self._search_memory(
            query_vec=query_vec,
            user_id=user_id,
            workspace_id=workspace_id,
            capability=capability,
            model_config=model_config,
            data_version=data_version,
            threshold=sim_threshold,
        )

    def set(
        self,
        query: str,
        value: Any,
        capability: str,
        user_id: str,
        workspace_id: str,
        data_version: str = "v1",
        model_config: str = "qwen2.5:7b",
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """
        Stores semantic query vector and payload in Redis Stack and fallback store.
        """
        if not settings.CACHE_SEMANTIC_ENABLED or not query:
            return False

        json_str = cache_serializer.serialize(value)
        if not json_str:
            return False

        try:
            query_vec = embedding_service.generate_embedding(query)
        except Exception as e:
            logger.warning(f"[SemanticCache] Embedding generation error during set: {e}")
            return False

        ttl = ttl_seconds or cache_policy.get_capability_ttl(capability)
        doc_key = (
            f"{settings.CACHE_NAMESPACE}:{settings.CACHE_SCHEMA_VERSION}:semantic:"
            f"user:{user_id}:ws:{workspace_id}:{capability}:v{data_version}:{hash(query) & 0xFFFFFFFF}"
        )

        # Redis HSET + EXPIRE
        if redis_client.is_connected:
            raw_client = redis_client.get_raw_client()
            if raw_client:
                try:
                    vec_bytes = struct.pack(f"{len(query_vec)}f", *query_vec)
                    raw_client.hset(
                        doc_key,
                        mapping={
                            "user_id": str(user_id),
                            "workspace_id": str(workspace_id),
                            "capability": capability,
                            "model_config": model_config,
                            "data_version": data_version,
                            "cache_key": doc_key,
                            "result_json": json_str,
                            "created_at": time.time(),
                            "vector": vec_bytes,
                        },
                    )
                    raw_client.expire(doc_key, ttl)
                except Exception as ex:
                    logger.warning(f"[SemanticCache] Redis HSET failed: {ex}")

        # In-memory store fallback
        expire_at = time.time() + ttl
        self._memory_store[doc_key] = {
            "user_id": str(user_id),
            "workspace_id": str(workspace_id),
            "capability": capability,
            "model_config": model_config,
            "data_version": data_version,
            "vector": query_vec,
            "result_json": json_str,
            "expire_at": expire_at,
        }
        return True

    def _search_memory(
        self,
        query_vec: List[float],
        user_id: str,
        workspace_id: str,
        capability: str,
        model_config: str,
        data_version: str,
        threshold: float,
    ) -> Optional[Tuple[Any, float]]:
        """Fallback in-memory cosine similarity search."""
        now = time.time()
        best_match = None
        best_sim = 0.0

        for key, rec in list(self._memory_store.items()):
            if now >= rec["expire_at"]:
                del self._memory_store[key]
                continue

            # Strict Multi-Tenant Isolation Filter Check
            if (
                rec["user_id"] == str(user_id)
                and rec["workspace_id"] == str(workspace_id)
                and rec["capability"] == capability
                and rec["model_config"] == model_config
                and rec["data_version"] == data_version
            ):
                sim = cosine_similarity(query_vec, rec["vector"])
                if sim > best_sim:
                    best_sim = sim
                    best_match = rec["result_json"]

        if best_sim >= threshold and best_match:
            payload = cache_serializer.deserialize(best_match)
            if payload is not None:
                logger.info(f"[SemanticCache] Fallback Memory HIT (score={best_sim:.4f} >= {threshold})")
                return payload, best_sim

        return None


semantic_cache = SemanticCache()
