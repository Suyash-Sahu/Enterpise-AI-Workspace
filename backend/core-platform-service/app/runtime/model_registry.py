import logging
from app.core.config import settings
from app.schemas.runtime import RuntimeModelInfo
from app.runtime.exceptions import UnsupportedModelError

logger = logging.getLogger(__name__)


class ModelRegistry:

    def __init__(self):
        self._local_models: set[str] = set(settings.RUNTIME_ALLOWED_MODELS_LOCAL)
        self._cloud_models: set[str] = set(settings.RUNTIME_ALLOWED_MODELS_CLOUD)

    def is_allowed_local(self, model: str) -> bool:
        if not model:
            return True
        return model.lower().strip() in {m.lower() for m in self._local_models}

    def is_allowed_cloud(self, model: str) -> bool:
        if not model:
            return True
        return model.lower().strip() in {m.lower() for m in self._cloud_models}

    def validate_model(self, model: str, runtime_mode: str) -> str:
        if not model:
            return settings.OLLAMA_DEFAULT_MODEL if runtime_mode == "local" else settings.LITELLM_DEFAULT_MODEL

        clean_model = model.strip()

        if runtime_mode == "local":
            if not self.is_allowed_local(clean_model):
                raise UnsupportedModelError(f"Model '{clean_model}' is not in the local allowlist. Allowed local models: {list(self._local_models)}")
        elif runtime_mode == "cloud":
            if not self.is_allowed_cloud(clean_model):
                raise UnsupportedModelError(f"Model '{clean_model}' is not in the cloud allowlist. Allowed cloud models: {list(self._cloud_models)}")
        return clean_model

    def get_all_allowlisted_models(self) -> list[RuntimeModelInfo]:
        models_info = []
        for m in settings.RUNTIME_ALLOWED_MODELS_LOCAL:
            models_info.append(
                RuntimeModelInfo(
                    model=m,
                    provider="ollama",
                    runtime="local",
                    available=True,
                )
            )
        for m in settings.RUNTIME_ALLOWED_MODELS_CLOUD:
            models_info.append(
                RuntimeModelInfo(
                    model=m,
                    provider="litellm",
                    runtime="cloud",
                    available=True,
                )
            )
        return models_info


model_registry = ModelRegistry()
