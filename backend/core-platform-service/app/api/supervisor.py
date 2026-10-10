import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.schemas.supervisor import SupervisorRequest
from app.services.supervisor_service import supervisor_service
from app.models.user import User
from app.utils.response import success_response, error_response

router = APIRouter()


@router.post("/execute")
def execute_supervisor_task(
    payload: SupervisorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Main P7 AMOF Supervisor orchestration endpoint.
    Extracts owner_id strictly from current_user.id.
    """
    start_time = time.time()
    try:
        response_data = supervisor_service.execute(db=db, request=payload, owner_id=str(current_user.id))
        return success_response(
            data=response_data.model_dump(),
            message="AMOF Supervisor orchestration completed successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Supervisor orchestration failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/classify")
def classify_intent(
    payload: SupervisorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Classifies intent capability for a user query (Authenticated).
    """
    start_time = time.time()
    try:
        intent_data = supervisor_service.classify(db=db, request=payload, owner_id=str(current_user.id))
        return success_response(
            data=intent_data.model_dump(),
            message="Intent classification completed",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Intent classification failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/plan")
def create_execution_plan(
    payload: SupervisorRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Generates DAG execution plan for a user query (Authenticated).
    """
    start_time = time.time()
    try:
        plan_data = supervisor_service.plan(db=db, request=payload, owner_id=str(current_user.id))
        return success_response(
            data=plan_data.model_dump(),
            message="Execution plan generated successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Plan generation failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.get("/health")
def supervisor_health():
    """
    Health check and operational telemetry for P7 AMOF Supervisor.
    """
    start_time = time.time()
    try:
        health_data = supervisor_service.health()
        return success_response(
            data=health_data.model_dump(),
            message="AMOF Supervisor operational status retrieved",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Supervisor health check failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )
