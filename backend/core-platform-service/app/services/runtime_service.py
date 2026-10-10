import logging
from app.schemas.runtime import (
    RuntimeGenerateRequest,
    RuntimeGenerateResponse,
    RuntimeHealthResponse,
    RuntimeModelInfo,
)
from app.runtime.policy import runtime_policy
from app.runtime.registry import runtime_registry
from app.runtime.model_registry import model_registry
from app.runtime.local_runtime import ollama_runtime
from app.runtime.cloud_runtime import litellm_runtime

logger = logging.getLogger(__name__)


class RuntimeService:

    @staticmethod
    def generate(request: RuntimeGenerateRequest) -> RuntimeGenerateResponse:
        """
        Main normalized model execution entrypoint for P6 Model Runtime Gateway.
        1. Validates policy boundaries (mode, model allowlist, temperature, max_tokens, timeout).
        2. Resolves RuntimeProvider (Ollama vs LiteLLM).
        3. Executes provider request and returns normalized RuntimeGenerateResponse.
        """
        # Validate policies and resolve placement. For execution_mode="auto"
        # this is where the privacy-constrained router picks local vs cloud.
        (
            resolved_mode,
            resolved_model,
            temp,
            max_tokens,
            timeout,
            decision,
        ) = runtime_policy.validate_request(request)

        # Update request object with clean parameters
        validated_request = RuntimeGenerateRequest(
            prompt=request.prompt,
            system_prompt=request.system_prompt,
            execution_mode=resolved_mode,
            model=resolved_model,
            temperature=temp,
            max_tokens=max_tokens,
            timeout=timeout,
            request_id=request.request_id,
            execution_id=request.execution_id,
            metadata=request.metadata,
        )

        provider = runtime_registry.get_provider(resolved_mode)
        logger.info(f"[P6 Gateway]: Executing prompt via '{resolved_mode}' runtime (model: {resolved_model})")

        response = provider.generate(validated_request)

        # Attach the routing decision so downstream persistence has the full
        # audit trail: what the content was classified as, which placements
        # that permitted, and why this candidate won. Without this the
        # non-leakage property is asserted rather than checkable.
        if decision is not None:
            response.routing = decision.to_audit_dict()

        return response

    @staticmethod
    def health() -> RuntimeHealthResponse:
        """
        Returns telemetry health status for Ollama and LiteLLM runtime clients.
        """
        ollama_ok = ollama_runtime.is_available()
        litellm_ok = litellm_runtime.is_available()

        models = model_registry.get_all_allowlisted_models()

        return RuntimeHealthResponse(
            status="online" if (ollama_ok or litellm_ok) else "degraded",
            ollama_status="online" if ollama_ok else "unavailable",
            litellm_status="online" if litellm_ok else "unavailable",
            available_models=models,
        )

    @staticmethod
    def list_models() -> list[RuntimeModelInfo]:
        """
        Returns list of allowlisted models.
        """
        return model_registry.get_all_allowlisted_models()


runtime_service = RuntimeService()
