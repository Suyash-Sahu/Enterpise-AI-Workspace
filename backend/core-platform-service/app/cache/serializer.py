"""
Project 9 — Safe JSON Cache Serializer
Handles JSON serialization of complex objects, datetimes, and Pydantic models.
Enforces 1 MB maximum payload cache limit (CACHE_MAX_RESULT_SIZE).
"""

from datetime import datetime, date
import json
import logging
from typing import Any, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)


class CacheSerializer:
    """
    JSON serializer/deserializer with size validation.
    """

    @staticmethod
    def default_encoder(obj: Any) -> Any:
        """Custom encoder for non-standard types."""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        if hasattr(obj, "dict"):
            return obj.dict()
        if hasattr(obj, "__str__"):
            return str(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    @classmethod
    def serialize(cls, data: Any) -> Optional[str]:
        """
        Serializes data to JSON string.
        Returns None if serialized payload exceeds CACHE_MAX_RESULT_SIZE (1 MB).
        """
        try:
            json_str = json.dumps(data, default=cls.default_encoder)
            encoded_bytes = json_str.encode("utf-8")
            if len(encoded_bytes) > settings.CACHE_MAX_RESULT_SIZE:
                logger.info(
                    f"[CacheSerializer] Payload size ({len(encoded_bytes)} bytes) exceeds "
                    f"maximum cache size ({settings.CACHE_MAX_RESULT_SIZE} bytes). Skipping cache."
                )
                return None
            return json_str
        except Exception as e:
            logger.warning(f"[CacheSerializer] Serialization error: {e}")
            return None

    @classmethod
    def deserialize(cls, json_str: str) -> Optional[Any]:
        """Deserializes JSON string to Python object."""
        if not json_str:
            return None
        try:
            return json.loads(json_str)
        except Exception as e:
            logger.warning(f"[CacheSerializer] Deserialization error: {e}")
            return None


cache_serializer = CacheSerializer()
