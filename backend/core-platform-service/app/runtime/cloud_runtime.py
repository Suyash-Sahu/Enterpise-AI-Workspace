import time
import json
import logging
import urllib.request
import urllib.error

from app.core.config import settings
from app.schemas.runtime import RuntimeGenerateRequest, RuntimeGenerateResponse, RuntimeModelInfo
from app.runtime.contracts import RuntimeProvider
from app.runtime.exceptions import RateLimitedError
from app.runtime.fallback import fallback_policy

logger = logging.getLogger(__name__)

# Client-side pacing floor for outbound OpenRouter/LiteLLM calls (2026-09-20
# rate-limit investigation): the free-tier cloud model the router prefers
# (cost_per_1k=$0, see RUNTIME_MODEL_PROFILES_CLOUD) carries a provider-side
# RPM ceiling well under what a sequential-but-unpaced benchmark can burst
# past -- a task's own multi-step chain (e.g. database_query's SQL-gen +
# explanation calls) or several tasks' cloud calls landing seconds apart is
# enough to trip it. This is a single module-level "earliest next call"
# gate -- every caller (main run, baselines, ablations, CDRP replans) funnels
# through this one generate() method, so one gate here paces all of them.
# Does not change routing, model selection, or retry/backoff -- only when
# the next outbound HTTP request is allowed to fire.
_MIN_CLOUD_CALL_INTERVAL_SECONDS = 4.0  # ~15 req/min, headroom under the ~20 RPM free-tier ceiling
_last_cloud_call_at: float = 0.0


class LiteLLMRuntime(RuntimeProvider):

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or settings.LITELLM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.OPENROUTER_API_KEY

    def generate(self, request: RuntimeGenerateRequest) -> RuntimeGenerateResponse:
        global _last_cloud_call_at
        wait = _MIN_CLOUD_CALL_INTERVAL_SECONDS - (time.time() - _last_cloud_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_cloud_call_at = time.time()

        start_time = time.time()
        model_name = request.model or settings.LITELLM_DEFAULT_MODEL

        # OpenRouter fallback target if standalone LiteLLM proxy is unavailable
        url = "https://openrouter.ai/api/v1/chat/completions" if "openrouter" in model_name or "gemma" in model_name or "gpt" in model_name else f"{self.base_url}/chat/completions"
        if not self.api_key and "openrouter" in url:
            url = f"{self.base_url}/chat/completions"

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": request.temperature or 0.2,
            "max_tokens": request.max_tokens or 1024,
        }

        req_data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if settings.OPENROUTER_API_KEY:
            headers["Authorization"] = f"Bearer {settings.OPENROUTER_API_KEY}"

        req = urllib.request.Request(
            url,
            data=req_data,
            headers=headers,
            method="POST",
        )

        try:
            timeout_sec = request.timeout or settings.RUNTIME_TIMEOUT
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                raw_res = json.loads(resp.read().decode("utf-8"))

            latency_ms = round((time.time() - start_time) * 1000, 2)
            choices = raw_res.get("choices", [])
            completion_text = choices[0].get("message", {}).get("content", "") if choices else ""

            usage = raw_res.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

            return RuntimeGenerateResponse(
                completion=completion_text,
                provider="litellm/openrouter",
                model=model_name,
                runtime="cloud",
                input_tokens=prompt_tokens,
                output_tokens=completion_tokens,
                total_tokens=total_tokens,
                latency_ms=latency_ms,
                finish_reason=choices[0].get("finish_reason", "stop") if choices else "stop",
                request_id=request.request_id,
                execution_id=request.execution_id,
            )
        except urllib.error.HTTPError as e:
            if e.code == 429:
                retry_after = None
                header_val = e.headers.get("Retry-After") if e.headers else None
                if header_val:
                    try:
                        retry_after = float(header_val)
                    except ValueError:
                        # Retry-After may be an HTTP-date instead of seconds;
                        # not worth parsing that format here -- the retry
                        # layer's own floor/ceiling covers this case.
                        retry_after = None
                raise RateLimitedError(
                    f"Cloud provider rate limit hit (HTTP 429): {e}",
                    retry_after=retry_after,
                ) from e
            fallback_policy.handle_cloud_failure(e)
        except Exception as e:
            fallback_policy.handle_cloud_failure(e)

    def is_available(self) -> bool:
        if settings.OPENROUTER_API_KEY:
            return True
        try:
            url = f"{self.base_url}/health"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> list[RuntimeModelInfo]:
        models = []
        for m in settings.RUNTIME_ALLOWED_MODELS_CLOUD:
            models.append(
                RuntimeModelInfo(
                    model=m,
                    provider="litellm/openrouter",
                    runtime="cloud",
                    available=True,
                )
            )
        return models


litellm_runtime = LiteLLMRuntime()
