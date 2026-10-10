"""
Regression tests (Phase 10 audit): a 140-task evaluation run hit OpenRouter
HTTP 429 responses repeatedly, and the generic retry backoff (0.5s, 1.0s)
retried straight into the same rate limit every time. These tests lock in
the fix: cloud_runtime.py now raises a distinguishable RateLimitedError
carrying the provider's Retry-After hint, execution_policy classifies it as
transient by type (not message wording), and RetryManager waits at least
RATE_LIMIT_MIN_DELAY_SECONDS (respecting a larger Retry-After hint, capped
at RATE_LIMIT_MAX_DELAY_SECONDS) before retrying -- never the short generic
backoff used for every other transient error.
"""
import email.message
import json
import time
import urllib.error
from unittest.mock import patch

from app.execution.policies import execution_policy
from app.execution.retry import (
    RetryManager,
    RATE_LIMIT_MIN_DELAY_SECONDS,
    RATE_LIMIT_MAX_DELAY_SECONDS,
)
import app.runtime.cloud_runtime as cloud_runtime
from app.runtime.cloud_runtime import LiteLLMRuntime
from app.runtime.exceptions import RateLimitedError
from app.schemas.runtime import RuntimeGenerateRequest


def _http_429(retry_after: str | None) -> urllib.error.HTTPError:
    headers = email.message.Message()
    if retry_after is not None:
        headers["Retry-After"] = retry_after
    return urllib.error.HTTPError(
        url="https://openrouter.ai/api/v1/chat/completions",
        code=429,
        msg="Too Many Requests",
        hdrs=headers,
        fp=None,
    )


def test_cloud_runtime_raises_rate_limited_error_with_retry_after_hint():
    runtime = LiteLLMRuntime(api_key="test-key")
    with patch("urllib.request.urlopen", side_effect=_http_429(retry_after="12")):
        try:
            runtime.generate(RuntimeGenerateRequest(prompt="hello", model="openai/gpt-4o-mini"))
            assert False, "expected RateLimitedError to be raised"
        except RateLimitedError as e:
            assert e.retry_after == 12.0


def test_cloud_runtime_rate_limited_error_without_header_has_no_hint():
    runtime = LiteLLMRuntime(api_key="test-key")
    with patch("urllib.request.urlopen", side_effect=_http_429(retry_after=None)):
        try:
            runtime.generate(RuntimeGenerateRequest(prompt="hello", model="openai/gpt-4o-mini"))
            assert False, "expected RateLimitedError to be raised"
        except RateLimitedError as e:
            assert e.retry_after is None


def test_rate_limited_error_is_classified_transient():
    assert execution_policy.is_transient_error(RateLimitedError("rate limited")) is True


def test_retry_manager_waits_at_least_the_floor_for_rate_limits():
    """
    No Retry-After hint: must wait RATE_LIMIT_MIN_DELAY_SECONDS, not the
    generic 0.5s exponential backoff used for other transient errors.
    """
    attempts = {"n": 0}

    def flaky():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RateLimitedError("rate limited", retry_after=None)
        return "ok"

    with patch("app.execution.retry.time.sleep") as mock_sleep:
        result, retry_count = RetryManager.execute_with_retry(flaky, max_retries=2)

    assert result == "ok"
    assert retry_count == 1
    mock_sleep.assert_called_once()
    waited = mock_sleep.call_args[0][0]
    assert waited == RATE_LIMIT_MIN_DELAY_SECONDS


def test_retry_manager_respects_larger_retry_after_hint_up_to_the_ceiling():
    def always_rate_limited():
        raise RateLimitedError("rate limited", retry_after=RATE_LIMIT_MAX_DELAY_SECONDS + 100)

    with patch("app.execution.retry.time.sleep") as mock_sleep:
        try:
            RetryManager.execute_with_retry(always_rate_limited, max_retries=1)
            assert False, "expected the error to propagate after exhausting retries"
        except RateLimitedError:
            pass

    waited = mock_sleep.call_args[0][0]
    assert waited == RATE_LIMIT_MAX_DELAY_SECONDS, "a huge Retry-After hint must be capped, not obeyed verbatim"


class _FakeCloudResponse:
    """Minimal context-manager stand-in for urllib's response object."""

    def __init__(self, payload: dict):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _ok_cloud_response() -> _FakeCloudResponse:
    return _FakeCloudResponse({
        "choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })


def test_cloud_runtime_paces_back_to_back_calls():
    """
    Regression (2026-09-20 rate-limit investigation): every evaluation loop
    (main run, baselines, ablations) issues OpenRouter calls back-to-back
    with zero spacing, and the free-tier model the router prefers has a low
    provider-side RPM ceiling that a sequential-but-unpaced benchmark can
    still burst past. LiteLLMRuntime.generate() now enforces
    _MIN_CLOUD_CALL_INTERVAL_SECONDS between successive outbound calls,
    regardless of which caller triggered them. Uses real wall-clock
    timestamps (fast -- only time.sleep is mocked, so this test does not
    actually wait) rather than a scripted time.time() sequence, so it stays
    correct regardless of how many internal time.time() calls generate()
    happens to make.
    """
    runtime = LiteLLMRuntime(api_key="test-key")
    cloud_runtime._last_cloud_call_at = 0.0  # simulate "no prior call" (epoch)
    try:
        with patch("urllib.request.urlopen", return_value=_ok_cloud_response()), \
             patch.object(cloud_runtime.time, "sleep") as mock_sleep:
            runtime.generate(RuntimeGenerateRequest(prompt="first", model="openai/gpt-4o-mini"))
            # No prior call recorded (epoch) -> nothing to pace against yet.
            mock_sleep.assert_not_called()

            runtime.generate(RuntimeGenerateRequest(prompt="second", model="openai/gpt-4o-mini"))
            # The two calls land a fraction of a real second apart -- well
            # under the floor -- so the second call must wait.
            mock_sleep.assert_called_once()
            waited = mock_sleep.call_args[0][0]
            assert 0 < waited <= cloud_runtime._MIN_CLOUD_CALL_INTERVAL_SECONDS
    finally:
        cloud_runtime._last_cloud_call_at = 0.0


def test_cloud_runtime_does_not_pace_when_interval_already_elapsed():
    """A call arriving after the interval has already passed must not sleep."""
    runtime = LiteLLMRuntime(api_key="test-key")
    with patch("urllib.request.urlopen", return_value=_ok_cloud_response()), \
         patch.object(cloud_runtime.time, "sleep") as mock_sleep:
        cloud_runtime._last_cloud_call_at = time.time() - (cloud_runtime._MIN_CLOUD_CALL_INTERVAL_SECONDS + 1.0)
        runtime.generate(RuntimeGenerateRequest(prompt="third", model="openai/gpt-4o-mini"))
        mock_sleep.assert_not_called()
    cloud_runtime._last_cloud_call_at = 0.0
