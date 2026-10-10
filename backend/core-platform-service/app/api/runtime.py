import time
from fastapi import APIRouter
from app.schemas.runtime import RuntimeGenerateRequest
from app.services.runtime_service import runtime_service
from app.utils.response import success_response, error_response

router = APIRouter()


@router.post("/generate")
def generate_completion(payload: RuntimeGenerateRequest):
    """
    Developer / Internal testing endpoint to execute text completion through P6 Model Runtime Gateway.
    Note: Normal application workflows execute strictly via P5 Execution Manager (/api/v1/execution-manager/execute).
    """
    start_time = time.time()
    try:
        response_data = runtime_service.generate(payload)
        return success_response(
            data=response_data.model_dump(),
            message="Runtime model completion generated successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Model runtime execution failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.get("/health")
def runtime_health():
    """
    Health check and telemetry status for P6 Ollama & LiteLLM runtimes.
    """
    start_time = time.time()
    try:
        health_data = runtime_service.health()
        return success_response(
            data=health_data.model_dump(),
            message="Model Runtime Gateway operational status retrieved",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Runtime health check failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.get("/models")
def list_runtime_models():
    """
    Lists all allowlisted local and cloud models exposed by P6.
    """
    start_time = time.time()
    try:
        models_data = runtime_service.list_models()
        return success_response(
            data={"models": [m.model_dump() for m in models_data]},
            message="Allowlisted runtime models retrieved successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Failed to list runtime models",
            exc=e,
            start_time=start_time,
            status_code=500,
        )
