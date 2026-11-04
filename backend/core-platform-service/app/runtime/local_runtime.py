import threading
import time
import json
import logging
import urllib.request
import urllib.error

from app.core.config import settings
from app.schemas.runtime import RuntimeGenerateRequest, RuntimeGenerateResponse, RuntimeModelInfo
from app.runtime.contracts import RuntimeProvider
from app.runtime.fallback import fallback_policy

logger = logging.getLogger(__name__)

# Phase 27: Local runtime concurrency semaphore (defaults to 1 to prevent VRAM thrashing)
_local_runtime_semaphore = threading.Semaphore(settings.LOCAL_RUNTIME_MAX_CONCURRENCY)


class OllamaRuntime(RuntimeProvider):

    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    def generate(self, request: RuntimeGenerateRequest) -> RuntimeGenerateResponse:
        start_time = time.time()
        model_name = request.model or settings.OLLAMA_DEFAULT_MODEL
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": model_name,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature or 0.2,
                "num_predict": request.max_tokens or 1024,
                "num_ctx": settings.OLLAMA_NUM_CTX,
            },
            "keep_alive": getattr(settings, "OLLAMA_KEEP_ALIVE", "15m"),
        }
        if request.system_prompt:
            payload["system"] = request.system_prompt

        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        timeout_sec = request.timeout or settings.RUNTIME_TIMEOUT
        max_retries = 2
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                with _local_runtime_semaphore:
                    with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                        raw_res = json.loads(resp.read().decode("utf-8"))
                        break
            except (urllib.error.URLError, ConnectionResetError, TimeoutError) as e:
                last_error = e
                if attempt < max_retries:
                    backoff = 0.5 * (attempt + 1)
                    logger.warning("[OllamaRuntime] Transient error on attempt %d: %s. Retrying in %.1fs...", attempt + 1, e, backoff)
                    time.sleep(backoff)
                else:
                    logger.error("[OllamaRuntime] Failed after %d attempts: %s", max_retries + 1, e)
            except Exception as e:
                last_error = e
                break

        if last_error and 'raw_res' not in locals():
            fallback_policy.handle_local_failure(last_error)

        try:

            latency_ms = round((time.time() - start_time) * 1000, 2)
            completion_text = raw_res.get("response", "")
            eval_count = raw_res.get("eval_count", 0)
            prompt_eval_count = raw_res.get("prompt_eval_count", 0)

            return RuntimeGenerateResponse(
                completion=completion_text,
                provider="ollama",
                model=model_name,
                runtime="local",
                input_tokens=prompt_eval_count,
                output_tokens=eval_count,
                total_tokens=prompt_eval_count + eval_count,
                latency_ms=latency_ms,
                finish_reason="stop",
                request_id=request.request_id,
                execution_id=request.execution_id,
            )
        except Exception as e:
            fallback_policy.handle_local_failure(e)

    def warmup(self, model: str | None = None) -> bool:
        """Primes the model into memory with configured keep_alive."""
        model_name = model or settings.OLLAMA_DEFAULT_MODEL
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": model_name,
                "prompt": "",
                "keep_alive": getattr(settings, "OLLAMA_KEEP_ALIVE", "15m"),
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10.0) as resp:
                return resp.status == 200
        except Exception as e:
            logger.debug("[OllamaRuntime] Model warm-up skipped or failed: %s", e)
            return False

    def is_available(self) -> bool:
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def list_models(self) -> list[RuntimeModelInfo]:
        try:
            url = f"{self.base_url}/api/tags"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = []
                for item in data.get("models", []):
                    m_name = item.get("name", "")
                    models.append(
                        RuntimeModelInfo(
                            model=m_name,
                            provider="ollama",
                            runtime="local",
                            available=True,
                        )
                    )
                return models
        except Exception:
            return []


ollama_runtime = OllamaRuntime()
