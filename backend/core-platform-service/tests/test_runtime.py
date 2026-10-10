import pytest
from app.core.config import settings
from app.schemas.runtime import RuntimeGenerateRequest, RuntimeMode
from app.runtime.model_registry import model_registry
from app.runtime.policy import runtime_policy
from app.runtime.exceptions import UnsupportedModelError, RuntimePolicyError, ProviderUnavailableError
from app.runtime.fallback import fallback_policy
from app.services.runtime_service import runtime_service


def test_model_registry_allowlist():
    # 1. Local allowlist
    assert model_registry.is_allowed_local("qwen2.5:7b") is True
    assert model_registry.is_allowed_local("qwen2.5:3b-instruct") is True
    assert model_registry.is_allowed_local("unapproved-local-model") is False

    # 2. Cloud allowlist
    assert model_registry.is_allowed_cloud("openai/gpt-4o-mini") is True
    assert model_registry.is_allowed_cloud("google/gemma-4-26b-a4b-it:free") is True
    assert model_registry.is_allowed_cloud("unapproved-cloud-model") is False

    # 3. Model validation raises UnsupportedModelError on invalid models
    with pytest.raises(UnsupportedModelError):
        model_registry.validate_model("unknown-model-xyz", "local")

    with pytest.raises(UnsupportedModelError):
        model_registry.validate_model("unknown-model-xyz", "cloud")


def test_runtime_policy_validation():
    # 1. Empty prompt raises RuntimePolicyError
    with pytest.raises(RuntimePolicyError):
        runtime_policy.validate_request(RuntimeGenerateRequest(prompt=""))

    # 2. Invalid temperature raises RuntimePolicyError
    with pytest.raises(RuntimePolicyError):
        runtime_policy.validate_request(RuntimeGenerateRequest(prompt="Hello", temperature=3.5))

    # 3. Valid parameters resolved cleanly
    # validate_request now also returns the routing decision. It is None here
    # because this request pins local: the router only runs for "auto", and for
    # an explicit cloud request where the privacy constraint must be checked.
    mode, model, temp, tokens, timeout, decision = runtime_policy.validate_request(
        RuntimeGenerateRequest(prompt="Hello P6", execution_mode=RuntimeMode.LOCAL, temperature=0.5, max_tokens=200, timeout=45.0)
    )
    assert decision is None
    assert mode == "local"
    assert model == settings.OLLAMA_DEFAULT_MODEL
    assert temp == 0.5
    assert tokens == 200
    assert timeout == 45.0


def test_strict_local_privacy_boundary():
    """
    STRICT LOCAL PRIVACY BOUNDARY TEST:
    Verifies that if a local request fails, FallbackPolicy raises ProviderUnavailableError directly
    and NEVER falls back to cloud providers.
    """
    with pytest.raises(ProviderUnavailableError) as exc_info:
        fallback_policy.handle_local_failure(Exception("Connection refused to Ollama :11434"))

    assert "privacy protection" in str(exc_info.value).lower()
    assert "refusing cloud fallback" in str(exc_info.value).lower() or "do not fall back to cloud" in str(exc_info.value).lower()


def test_runtime_service_health():
    health = runtime_service.health()
    assert health.status in ("online", "degraded", "unavailable")
    assert len(health.available_models) >= 2
