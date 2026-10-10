import logging
from app.runtime.contracts import RuntimeProvider
from app.runtime.local_runtime import ollama_runtime
from app.runtime.cloud_runtime import litellm_runtime
from app.runtime.exceptions import UnsupportedModelError

logger = logging.getLogger(__name__)


class RuntimeRegistry:

    def __init__(self):
        self._providers: dict[str, RuntimeProvider] = {}
        self._register_default_runtimes()

    def _register_default_runtimes(self):
        self.register("local", ollama_runtime)
        self.register("cloud", litellm_runtime)

    def register(self, runtime_name: str, provider: RuntimeProvider):
        clean_name = runtime_name.lower().strip()
        self._providers[clean_name] = provider
        logger.info(f"Registered P6 model runtime provider: '{clean_name}'")

    def get_provider(self, runtime_mode: str) -> RuntimeProvider:
        clean_mode = runtime_mode.lower().strip() if runtime_mode else "local"
        if clean_mode not in self._providers:
            raise UnsupportedModelError(f"Unsupported runtime mode '{runtime_mode}'. Registered runtimes: {list(self._providers.keys())}")
        return self._providers[clean_mode]


runtime_registry = RuntimeRegistry()
