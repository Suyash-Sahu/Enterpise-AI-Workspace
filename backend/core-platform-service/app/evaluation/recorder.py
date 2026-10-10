from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationRun, EvaluationTask, EvaluationResult, EvaluationMetric
from app.evaluation.schemas import EvaluationResultItemSchema, MetricSummarySchema

from app.utils.timeutils import utcnow_naive


class EvaluationRecorder:
    """
    Persists evaluation runs, task-level execution traces, item results, and derived metrics to PostgreSQL database.
    """

    @staticmethod
    def create_run(
        db: Session,
        run_id: str,
        dataset_version: str,
        dataset_hash: str,
        config_dict: Dict[str, Any],
        config_hash: Optional[str] = None,
        git_commit: Optional[str] = None,
    ) -> EvaluationRun:
        run = EvaluationRun(
            run_id=run_id,
            status="running",
            dataset_version=dataset_version,
            dataset_hash=dataset_hash,
            configuration_hash=config_hash,
            started_at=utcnow_naive(),
            task_count=0,
            completed_count=0,
            failed_count=0,
            configuration_json=config_dict,
            git_commit=git_commit,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def save_tasks(db: Session, run_id: str, tasks: List[Dict[str, Any]]) -> None:
        db_tasks = []
        for t in tasks:
            db_task = EvaluationTask(
                run_id=run_id,
                task_id=t["task_id"],
                task_text=t["task"],
                category=t["category"],
                complexity=t["complexity"],
                privacy_level=t["privacy_level"],
                expected_capability=t["expected_capability"],
                expected_execution_mode=t["expected_execution_mode"],
                expected_approval=t.get("expected_approval_requirement", False),
            )
            db_tasks.append(db_task)
        db.bulk_save_objects(db_tasks)
        db.commit()

    @staticmethod
    def save_result(db: Session, run_id: str, item: EvaluationResultItemSchema) -> EvaluationResult:
        res = EvaluationResult(
            run_id=run_id,
            task_id=item.task_id,
            status="COMPLETED" if item.completion_success else "FAILED",
            actual_capability=item.actual_capability,
            actual_execution_mode=item.actual_execution_mode,
            actual_model=item.actual_model,
            routing_correct=item.routing_correct,
            capability_correct=item.capability_correct,
            approval_required=item.approval_required,
            approval_status=item.approval_status,
            execution_blocked=item.execution_blocked,
            approval_guard_triggered=item.approval_guard_triggered,
            cache_hit=item.cache_hit,
            verification_status=item.verification_status,
            started_at=item.started_at or utcnow_naive(),
            completed_at=item.completed_at or utcnow_naive(),
            latency_ms=item.latency_ms,
            input_tokens=item.input_tokens,
            output_tokens=item.output_tokens,
            total_tokens=item.total_tokens,
            estimated_cost=item.estimated_cost,
            privacy_classification=item.privacy_classification,
            privacy_confidence=item.privacy_confidence,
            cloud_execution=item.cloud_execution,
            completion_success=item.completion_success,
            output_quality_score=item.output_quality_score,
            error_type=item.error_type,
            error_message=item.error_message,
            trace_json=item.trace_json,
        )
        db.add(res)
        db.commit()
        db.refresh(res)
        return res

    @staticmethod
    def save_metrics(db: Session, run_id: str, metrics: List[MetricSummarySchema]) -> None:
        db_metrics = []
        for m in metrics:
            db_metric = EvaluationMetric(
                run_id=run_id,
                metric_name=m.metric_name,
                metric_value=m.metric_value,
                denominator=m.denominator,
                numerator=m.numerator,
                metric_status=m.metric_status,
                metric_metadata=m.metric_metadata,
            )
            db_metrics.append(db_metric)
        db.bulk_save_objects(db_metrics)
        db.commit()

    @staticmethod
    def update_run_status(
        db: Session,
        run_id: str,
        status: str,
        task_count: int,
        completed_count: int,
        failed_count: int,
    ) -> EvaluationRun:
        run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
        if run:
            run.status = status
            run.task_count = task_count
            run.completed_count = completed_count
            run.failed_count = failed_count
            run.completed_at = utcnow_naive()
            db.commit()
            db.refresh(run)
        return run
