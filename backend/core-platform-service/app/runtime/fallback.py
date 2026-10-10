import logging
from app.runtime.exceptions import ProviderUnavailableError

logger = logging.getLogger(__name__)


class FallbackPolicy:

    @staticmethod
    def handle_local_failure(error: Exception):
        """
        STRICT LOCAL PRIVACY BOUNDARY:
        If an execution request was explicitly assigned 'local' mode and Ollama fails,
        DO NOT fall back to cloud providers (prevents leaking private workspace docs).
        Raise ProviderUnavailableError directly.
        """
        logger.error(f"[Local Privacy Boundary Enforced]: Local Ollama runtime failed ({error}). Refusing cloud fallback.")
        raise ProviderUnavailableError(f"Local Ollama runtime unavailable: {str(error)}. Local requests do not fall back to cloud for privacy protection.")

    @staticmethod
    def handle_cloud_failure(error: Exception):
        """
        Cloud failure policy: raise ProviderUnavailableError or trigger cloud secondary fallback.
        """
        logger.warning(f"[Cloud Runtime Failure]: Cloud provider failed ({error}).")
        raise ProviderUnavailableError(f"Cloud model runtime provider unavailable: {str(error)}")


fallback_policy = FallbackPolicy()
