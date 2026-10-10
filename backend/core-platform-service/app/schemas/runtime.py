from enum import Enum
from typing import Optional, Any
from pydantic import BaseModel, Field


class RuntimeMode(str, Enum):
    AUTO = "auto"
    LOCAL = "local"
    CLOUD = "cloud"


class RuntimeGenerateRequest(BaseModel):
    prompt: str = Field(..., description="User query or prompt text for model completion", json_schema_extra={"example": "Explain RAG in simple terms."})
    system_prompt: Optional[str] = Field(default=None, description="Optional system instructions")
    execution_mode: Optional[RuntimeMode] = Field(default=RuntimeMode.AUTO, description="Desired execution mode: local, cloud, auto")
    model: Optional[str] = Field(default=None, description="Specific model name requested from allowlist")
    temperature: Optional[float] = Field(default=0.2, description="Sampling temperature (0.0 to 2.0)")
    max_tokens: Optional[int] = Field(default=1024, description="Maximum tokens to generate")
    timeout: Optional[float] = Field(default=60.0, description="Runtime execution timeout in seconds")
    request_id: Optional[str] = Field(default=None, description="Correlation trace request ID from P5 Execution Manager")
    execution_id: Optional[str] = Field(default=None, description="P5 Execution record ID")
    metadata: Optional[dict[str, Any]] = Field(default=None, description="Task context metadata")


class RuntimeGenerateResponse(BaseModel):
    completion: str = Field(..., description="Generated completion text output")
    provider: str = Field(..., description="Resolved model provider (ollama, litellm, openrouter)")
    model: str = Field(..., description="Resolved model name")
    runtime: str = Field(..., description="Execution runtime (local or cloud)")
    input_tokens: int = Field(default=0, description="Input prompt token count")
    output_tokens: int = Field(default=0, description="Generated output token count")
    total_tokens: int = Field(default=0, description="Total tokens used")
    latency_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    finish_reason: str = Field(default="stop", description="Completion termination reason")
    request_id: Optional[str] = Field(default=None, description="Trace request ID")
    execution_id: Optional[str] = Field(default=None, description="P5 Execution ID")
    routing: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Audit record of the privacy-constrained routing decision: the "
            "classified sensitivity label, which placements were permitted, and "
            "which candidates were rejected and why. Present when the router "
            "ran; None when the caller pinned local execution."
        ),
    )


class RuntimeModelInfo(BaseModel):
    model: str
    provider: str
    runtime: str
    available: bool
    capabilities: list[str] = Field(default_factory=lambda: ["text_generation"])


class RuntimeHealthResponse(BaseModel):
    status: str
    ollama_status: str
    litellm_status: str
    available_models: list[RuntimeModelInfo]
