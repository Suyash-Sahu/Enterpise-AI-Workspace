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
            }
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

        try:
            timeout_sec = request.timeout or settings.RUNTIME_TIMEOUT
            with _local_runtime_semaphore:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    raw_res = json.loads(resp.read().decode("utf-8"))

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
