"""
Execution Manager API.

M17c  Every route here hardcoded `owner_id = "1"`, one of them under a
      docstring promising "tenant-isolated execution history for
      current_user.id". The service layer does isolate correctly — it filters
      every query on owner_id — but the API layer never passed the caller
      through, so the isolation had nothing to isolate on.

      The effect was a cross-tenant read: GET /history returned user 1's
      executions to whoever asked, and executions carry input_json and
      result_json — prompts, generated SQL, retrieved document content. In the
      other direction every user's own executions were invisible to them,
      because they were being looked up under an owner they were not.

      The caller now comes from the authenticated session, the same way
      SupervisorContext.resolve_user_id refuses to guess at one.
"""

import time
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.database import get_db
from app.models.user import User
from app.schemas.execution import ExecutionRequest
from app.services.execution_manager import execution_manager
from app.utils.response import success_response, error_response

router = APIRouter()


@router.post("/execute")
def execute_task(
    payload: ExecutionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Main endpoint to submit and execute an AI capability task synchronously.
    Supported task_type values: rag_search, rag_answer, database_query, text_generation, document_summary.
    """
    start_time = time.time()
    try:
        owner_id = str(current_user.id)

        response_data = execution_manager.execute(
            db=db,
            request=payload,
            owner_id=owner_id,
        )

        return success_response(
            data=response_data.model_dump(),
            message="Task executed successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Execution failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.get("/status/{execution_id}")
def get_execution_status(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves execution status for a specific execution ID.
    """
    start_time = time.time()
    try:
        owner_id = str(current_user.id)
        status_data = execution_manager.get_status(
            db=db,
            execution_id=execution_id,
            owner_id=owner_id,
        )
        return success_response(
            data=status_data.model_dump(),
            message="Execution status retrieved successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Failed to retrieve execution status",
            exc=e,
            start_time=start_time,
            status_code=404 if "not found" in str(e).lower() else 500,
        )


@router.get("/history")
def get_execution_history(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retrieves execution history for the authenticated caller only.
    """
    start_time = time.time()
    try:
        owner_id = str(current_user.id)
        history_data = execution_manager.get_history(
            db=db,
            owner_id=owner_id,
            limit=limit,
        )
        return success_response(
            data=history_data.model_dump(),
            message="Execution history retrieved successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Failed to retrieve execution history",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/cancel/{execution_id}")
def cancel_execution(
    execution_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancels an active execution.
    """
    start_time = time.time()
    try:
        owner_id = str(current_user.id)
        cancelled_data = execution_manager.cancel(
            db=db,
            execution_id=execution_id,
            owner_id=owner_id,
        )
        return success_response(
            data=cancelled_data.model_dump(),
            message="Execution cancelled successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Failed to cancel execution",
            exc=e,
            start_time=start_time,
            status_code=400,
        )


@router.get("/health")
def execution_manager_health():
    """
    Health check and telemetry endpoint for P5 AI Execution Manager.
    """
    start_time = time.time()
    try:
        health_data = execution_manager.get_health()
        return success_response(
            data=health_data,
            message="AI Execution Manager is operational",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Execution Manager health check failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )
