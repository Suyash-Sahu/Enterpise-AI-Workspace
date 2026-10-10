class RuntimeError(Exception):
    """Base runtime exception for P6 Model Runtime Gateway."""


class ProviderUnavailableError(RuntimeError):
    """Raised when Ollama or LiteLLM service connection fails."""


class RateLimitedError(ProviderUnavailableError):
    """
    Raised specifically for an HTTP 429 from a cloud provider (Phase 10
    audit: a 140-task evaluation run hit OpenRouter 429s repeatedly, retried
    on the same 0.5s/1.0s generic backoff used for every other transient
    error, and kept failing). Carries the provider's own Retry-After hint
    (seconds) when present, so the retry layer can wait long enough for the
    rate limit to actually clear instead of guessing.
    """

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ModelNotFoundError(RuntimeError):
    """Raised when the requested model is not found or not installed."""


class RuntimeTimeoutError(RuntimeError):
    """Raised when model execution exceeds the specified timeout limit."""


class RuntimePolicyError(RuntimeError):
    """Raised when request parameters violate runtime policy boundaries."""


class ProviderAuthenticationError(RuntimeError):
    """Raised when provider API authentication fails."""


class UnsupportedModelError(RuntimeError):
    """Raised when a model is not listed in the allowlist."""


class RuntimeConfigurationError(RuntimeError):
    """Raised when runtime setup configuration is invalid."""
