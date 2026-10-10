import json
import logging
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.core.config import settings
from app.models.execution import Execution
from app.schemas.execution import (
    ExecutionRequest,
    ExecutionResponse,
    ExecutionStatusResponse,
    ExecutionHistoryResponse,
    ExecutionStatus,
)
from app.execution.executor import execution_executor
from app.execution.registry import task_registry

logger = logging.getLogger(__name__)


class ExecutionManager:

    @staticmethod
    def execute(db: Session, request: ExecutionRequest, owner_id: str) -> ExecutionResponse:
        """
        Public entrypoint to submit and execute an AI task.
        """
        return execution_executor.execute_task(db=db, request=request, owner_id=owner_id)

    @staticmethod
    def get_status(db: Session, execution_id: str, owner_id: str) -> ExecutionStatusResponse:
        """
        Retrieves current status of an execution record with strict tenant isolation.
        """
        record = db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.owner_id == str(owner_id),
        ).first()

        if not record:
            raise ValueError(f"Execution record '{execution_id}' not found or access denied")

        return ExecutionStatusResponse(
            execution_id=record.id,
            status=ExecutionStatus(record.status),
            task_type=record.task_type,
            execution_mode=record.execution_mode,
            created_at=record.created_at.isoformat() if record.created_at else "",
            started_at=record.started_at.isoformat() if record.started_at else None,
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
            execution_time=record.execution_time,
            retry_count=record.retry_count,
            error_message=record.error_message,
        )

    @staticmethod
    def get_history(db: Session, owner_id: str, limit: int = 50) -> ExecutionHistoryResponse:
        """
        Retrieves tenant-isolated execution history for current_user.id.
        """
        capped_limit = min(max(1, limit), settings.EXECUTION_HISTORY_LIMIT)

        records = db.query(Execution).filter(
            Execution.owner_id == str(owner_id),
        ).order_by(desc(Execution.created_at)).limit(capped_limit).all()

        items: list[ExecutionResponse] = []
        for r in records:
            result_data = json.loads(r.result_json) if r.result_json else None
            items.append(
                ExecutionResponse(
                    execution_id=r.id,
                    status=ExecutionStatus(r.status),
                    task_type=r.task_type,
                    result=result_data,
                    provider=r.provider,
                    model=r.model,
                    execution_time=r.execution_time,
                    retry_count=r.retry_count,
                    idempotency_key=r.idempotency_key,
                    request_id=r.request_id,
                    error_type=r.error_type,
                    error_message=r.error_message,
                )
            )

        return ExecutionHistoryResponse(
            total=len(items),
            items=items,
        )

    @staticmethod
    def cancel(db: Session, execution_id: str, owner_id: str) -> ExecutionStatusResponse:
        """
        Cancels an execution if it has not completed yet.
        """
        record = db.query(Execution).filter(
            Execution.id == execution_id,
            Execution.owner_id == str(owner_id),
        ).first()

        if not record:
            raise ValueError(f"Execution record '{execution_id}' not found or access denied")

        if record.status in (ExecutionStatus.COMPLETED.value, ExecutionStatus.FAILED.value):
            raise ValueError(f"Cannot cancel execution '{execution_id}' in terminal state '{record.status}'")

        record.status = ExecutionStatus.CANCELLED.value
        db.commit()
        db.refresh(record)

        return ExecutionStatusResponse(
            execution_id=record.id,
            status=ExecutionStatus.CANCELLED,
            task_type=record.task_type,
            execution_mode=record.execution_mode,
            created_at=record.created_at.isoformat() if record.created_at else "",
            started_at=record.started_at.isoformat() if record.started_at else None,
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
            execution_time=record.execution_time,
            retry_count=record.retry_count,
            error_message="Cancelled by user",
        )

    @staticmethod
    def get_health() -> dict:
        """
        Returns telemetry health status for P5 Execution Manager.
        """
        return {
            "status": "online",
            "execution_manager_enabled": settings.EXECUTION_MANAGER_ENABLED,
            "supported_tasks": task_registry.list_supported_tasks(),
            "default_timeout_seconds": settings.EXECUTION_DEFAULT_TIMEOUT,
            "max_timeout_seconds": settings.EXECUTION_MAX_TIMEOUT,
            "max_retries": settings.EXECUTION_MAX_RETRIES,
            "history_limit": settings.EXECUTION_HISTORY_LIMIT,
        }


execution_manager = ExecutionManager()