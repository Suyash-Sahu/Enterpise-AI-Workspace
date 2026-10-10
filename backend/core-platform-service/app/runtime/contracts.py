from abc import ABC, abstractmethod
from app.schemas.runtime import RuntimeGenerateRequest, RuntimeGenerateResponse, RuntimeModelInfo


class RuntimeProvider(ABC):
    """
    Abstract interface for Model Runtime Gateway clients (Ollama, LiteLLM).
    Every provider MUST implement generate() and health() returning normalized data structures.
    """

    @abstractmethod
    def generate(self, request: RuntimeGenerateRequest) -> RuntimeGenerateResponse:
        """
        Executes text completion request synchronously and returns normalized RuntimeGenerateResponse.
        """

    @abstractmethod
    def is_available(self) -> bool:
        """
        Checks whether the provider service (Ollama or LiteLLM) is online and reachable.
        """

    @abstractmethod
    def list_models(self) -> list[RuntimeModelInfo]:
        """
        Lists available models exposed by this provider.
        """
