import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Keys containing sensitive credentials that must NEVER be persisted in raw execution JSON
SENSITIVE_KEYS = {
    "access_token",
    "refresh_token",
    "password",
    "secret",
    "api_key",
    "token",
    "client_secret",
}


class ExecutionMetrics:

    @staticmethod
    def sanitize_payload(data: Any) -> Any:
        """
        Recursively sanitizes dictionary payloads by redacting sensitive security keys.
        """
        if isinstance(data, dict):
            sanitized = {}
            for k, v in data.items():
                if k.lower() in SENSITIVE_KEYS:
                    sanitized[k] = "[REDACTED]"
                else:
                    sanitized[k] = ExecutionMetrics.sanitize_payload(v)
            return sanitized
        elif isinstance(data, list):
            return [ExecutionMetrics.sanitize_payload(item) for item in data]
        return data

    @staticmethod
    def to_json_str(data: Any) -> str:
        """
        Converts payload to sanitized JSON string.
        """
        if data is None:
            return "{}"
        try:
            sanitized = ExecutionMetrics.sanitize_payload(data)
            return json.dumps(sanitized, default=str)
        except Exception as e:
            logger.error(f"Error serializing execution payload JSON: {e}")
            return "{}"


execution_metrics = ExecutionMetrics()
