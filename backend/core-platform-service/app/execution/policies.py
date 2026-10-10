import logging
from app.core.config import settings
from app.runtime.exceptions import RuntimePolicyError, RateLimitedError

logger = logging.getLogger(__name__)

ALLOWED_MODES = {"auto", "local", "cloud"}


class ExecutionPolicy:

    @staticmethod
    def validate_mode(execution_mode: str) -> str:
        clean_mode = execution_mode.lower().strip() if execution_mode else "auto"
        if clean_mode not in ALLOWED_MODES:
            raise ValueError(f"Invalid execution_mode '{execution_mode}'. Allowed modes: {list(ALLOWED_MODES)}")
        return clean_mode

    @staticmethod
    def resolve_timeout(requested_timeout: float | None) -> float:
        if requested_timeout is None:
            return settings.EXECUTION_DEFAULT_TIMEOUT
        return min(max(1.0, requested_timeout), settings.EXECUTION_MAX_TIMEOUT)

    @staticmethod
    def is_transient_error(error: Exception) -> bool:
        """
        Classifies whether an exception is transient (and suitable for retry) or permanent.
        """
        err_msg = str(error).lower()

        # A policy refusal is a decision, not a failure. Retrying a privacy
        # refusal re-runs the classifier on identical content, gets the identical
        # answer, and burns the retry budget three times over before reporting
        # the same refusal. Permanent by type so the message wording cannot
        # accidentally make it transient.
        if isinstance(error, RuntimePolicyError):
            return False

        # A rate limit is explicitly transient by type, not by message
        # wording -- this is what the retry layer's Retry-After-aware
        # backoff (RATE_LIMIT_MIN/MAX_DELAY_SECONDS) actually keys off.
        if isinstance(error, RateLimitedError):
            return True

        # Validation & Auth errors are permanent - DO NOT RETRY
        if isinstance(error, (ValueError, TypeError, KeyError)):
            return False
        if any(token in err_msg for token in ["invalid", "unauthorized", "forbidden", "schema", "validation"]):
            return False

        # Network / Provider timeouts & connection resets are transient - RETRY
        if any(token in err_msg for token in ["connection", "timeout", "unavailable", "503", "502", "reset", "rate limit"]):
            return True

        return True


execution_policy = ExecutionPolicy()
