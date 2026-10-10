"""
Project 9 — Idempotent Vector Index Manager
Initializes Redis Stack native vector index idx:semantic_cache on startup.
Dynamically sets vector dimension matching P3 EMBEDDING_DIM settings.
"""

import logging
from app.cache.client import redis_client
from app.core.config import settings

logger = logging.getLogger(__name__)

INDEX_NAME = "idx:semantic_cache"
DOC_PREFIX = f"{settings.CACHE_NAMESPACE}:{settings.CACHE_SCHEMA_VERSION}:semantic:"


def initialize_vector_index() -> bool:
    """
    Idempotently creates Redis Stack vector index idx:semantic_cache if missing.
    Matches P3 settings.EMBEDDING_DIM dynamically (e.g., 1536 for OpenAI).
    """
    if not redis_client.is_connected:
        logger.info("[VectorIndex] Redis not connected. Skipping vector index initialization.")
        return False

    raw_client = redis_client.get_raw_client()
    if not raw_client:
        return False

    try:
        # Check existing indexes using FT._LIST or FT.INFO
        try:
            indexes = raw_client.execute_command("FT._LIST")
            if isinstance(indexes, list) and (INDEX_NAME in indexes or INDEX_NAME.encode() in indexes):
                logger.info(f"[VectorIndex] Redis vector index '{INDEX_NAME}' already exists.")
                return True
        except Exception:
            # FT._LIST might not be supported or error out if index doesn't exist
            pass

        try:
            raw_client.execute_command("FT.INFO", INDEX_NAME)
            logger.info(f"[VectorIndex] Redis vector index '{INDEX_NAME}' verified.")
            return True
        except Exception:
            # Index does not exist; proceed to create
            pass

        dim = getattr(settings, "EMBEDDING_DIM", 1536)
        logger.info(f"[VectorIndex] Creating Redis vector index '{INDEX_NAME}' with DIM={dim}...")

        # FT.CREATE idx:semantic_cache ON HASH PREFIX 1 amof:v1:semantic: SCHEMA ...
        raw_client.execute_command(
            "FT.CREATE",
            INDEX_NAME,
            "ON",
            "HASH",
            "PREFIX",
            "1",
            DOC_PREFIX,
            "SCHEMA",
            "user_id",
            "TAG",
            "workspace_id",
            "TAG",
            "capability",
            "TAG",
            "model_config",
            "TAG",
            "data_version",
            "TAG",
            "cache_key",
            "TAG",
            "created_at",
            "NUMERIC",
            "vector",
            "VECTOR",
            "HNSW",
            "6",
            "TYPE",
            "FLOAT32",
            "DIM",
            str(dim),
            "DISTANCE_METRIC",
            "COSINE",
        )
        logger.info(f"[VectorIndex] Vector index '{INDEX_NAME}' successfully created.")
        return True

    except Exception as e:
        err_msg = str(e)
        if "already exists" in err_msg.lower():
            logger.info(f"[VectorIndex] Index '{INDEX_NAME}' already exists.")
            return True
        logger.warning(f"[VectorIndex] Could not initialize Redis Search vector index ({e}). Operating in basic mode.")
        return False
