import time
import logging
from typing import Callable, Any
from app.core.config import settings
from app.execution.policies import execution_policy
from app.runtime.exceptions import RateLimitedError

logger = logging.getLogger(__name__)

# A rate limit rarely clears in under a few seconds even with no Retry-After
# hint from the provider; the ceiling stops a bad/huge hint from stalling a
# single task for minutes. Phase 10 audit: the previous generic 0.5s/1.0s
# exponential backoff retried into the same OpenRouter 429 every time.
RATE_LIMIT_MIN_DELAY_SECONDS = 5.0
RATE_LIMIT_MAX_DELAY_SECONDS = 30.0


class RetryManager:

    @staticmethod
    def execute_with_retry(
        func: Callable[[], Any],
        max_retries: int | None = None,
        base_delay: float = 0.5,
    ) -> tuple[Any, int]:
        """
        Executes func with bounded retries and exponential backoff.
        Returns tuple of (result, retry_count).
        """
        retries = max_retries if max_retries is not None else settings.EXECUTION_MAX_RETRIES
        attempts = 0

        while attempts <= retries:
            try:
                result = func()
                return result, attempts
            except Exception as error:
                attempts += 1
                is_transient = execution_policy.is_transient_error(error)

                if attempts > retries or not is_transient:
                    logger.warning(f"Execution attempt {attempts}/{retries + 1} failed (transient={is_transient}): {error}")
                    raise error

                if isinstance(error, RateLimitedError):
                    # Respect the provider's own wait time when it gave one;
                    # otherwise assume the conservative floor. Either way,
                    # this is what actually gives the rate limit a chance to
                    # clear, instead of retrying on the same short backoff
                    # every other transient error uses.
                    server_hint = error.retry_after if error.retry_after is not None else RATE_LIMIT_MIN_DELAY_SECONDS
                    delay = min(max(server_hint, RATE_LIMIT_MIN_DELAY_SECONDS), RATE_LIMIT_MAX_DELAY_SECONDS)
                else:
                    delay = base_delay * (2 ** (attempts - 1))

                logger.info(f"Execution attempt {attempts} failed with transient error: {error}. Retrying in {delay}s...")
                time.sleep(delay)

        raise RuntimeError("RetryManager exceeded maximum attempts")


retry_manager = RetryManager()
