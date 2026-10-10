from sqlalchemy import (
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.base import Base

from app.utils.timeutils import utcnow_naive


class EvaluationRun(Base):
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), unique=True, index=True, nullable=False)
    status = Column(String(32), default="pending", index=True, nullable=False)  # pending, running, completed, failed, cancelled, dataset_required
    dataset_version = Column(String(64), nullable=False)
    dataset_hash = Column(String(64), nullable=False)
    configuration_hash = Column(String(64), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    task_count = Column(Integer, default=0)
    completed_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    configuration_json = Column(JSON, nullable=True)
    git_commit = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)
    # Set when save_artifacts() (JSON/CSV export) fails after the run itself
    # completed successfully. Previously that failure was only logged and the
    # run reported "completed" with no trace that its artifact files were
    # incomplete or missing (smoke-eval audit, 2026-09-20: evaluation_results.csv
    # was never written for any run since privacy_confidence was added, because
    # export_csv referenced a column that didn't exist on this model, and the
    # exception was swallowed here). NULL means artifact generation succeeded.
    artifact_error = Column(Text, nullable=True)

    tasks = relationship("EvaluationTask", back_populates="run", cascade="all, delete-orphan")
    results = relationship("EvaluationResult", back_populates="run", cascade="all, delete-orphan")
    metrics = relationship("EvaluationMetric", back_populates="run", cascade="all, delete-orphan")


class EvaluationTask(Base):
    __tablename__ = "evaluation_tasks"
    __table_args__ = (
        UniqueConstraint("run_id", "task_id", name="uq_eval_tasks_run_task"),
    )

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(64), nullable=False, index=True)
    task_text = Column(Text, nullable=False)
    category = Column(String(64), nullable=False)
    complexity = Column(String(32), nullable=False)
    privacy_level = Column(String(32), nullable=False)
    expected_capability = Column(String(64), nullable=False)
    expected_execution_mode = Column(String(32), nullable=False)
    expected_approval = Column(Boolean, default=False)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)

    run = relationship("EvaluationRun", back_populates="tasks")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(64), nullable=False, index=True)
    status = Column(String(32), default="pending", nullable=False)  # COMPLETED, FAILED, WAITING_FOR_APPROVAL
    actual_capability = Column(String(64), nullable=True)
    actual_execution_mode = Column(String(32), nullable=True)  # local, cloud
    actual_model = Column(String(64), nullable=True)
    routing_correct = Column(Boolean, nullable=True)
    # Whether the classified/executed capability matched the dataset's
    # expected_capability -- independent of routing_correct, which only ever
    # compares local/cloud PLACEMENT (see app/evaluation/executor.py). Added
    # 2026-09-20 after the smoke evaluation found routing_correct=True rows
    # whose actual capability was entirely wrong (a rag_answer task executed
    # as database_query still "correctly" landed local, so routing_correct
    # alone hid the capability misclassification).
    capability_correct = Column(Boolean, nullable=True)
    approval_required = Column(Boolean, nullable=True)
    approval_status = Column(String(32), nullable=True)  # NOT_REQUIRED, APPROVED, REJECTED, PENDING
    execution_blocked = Column(Boolean, nullable=True)
    approval_guard_triggered = Column(Boolean, nullable=True)
    cache_hit = Column(Boolean, nullable=True)
    verification_status = Column(String(32), nullable=True)  # PASSED, FAILED, SKIPPED
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    latency_ms = Column(Float, nullable=True)
    input_tokens = Column(Integer, nullable=True)
    output_tokens = Column(Integer, nullable=True)
    total_tokens = Column(Integer, nullable=True)
    estimated_cost = Column(Float, nullable=True)
    privacy_classification = Column(String(32), nullable=True)
    # The classifier's confidence for privacy_classification above. Existed
    # on EvaluationResultItemSchema and was computed by TaskExecutor since
    # 2026-09-12, but was never added to this table -- silently dropped on
    # every save_result() call, and export_csv() (which assumed the column
    # existed) crashed reading it, breaking CSV artifact generation for
    # every run since. Fixed 2026-09-20.
    privacy_confidence = Column(Float, nullable=True)
    cloud_execution = Column(Boolean, nullable=True)
    completion_success = Column(Boolean, nullable=True)
    output_quality_score = Column(Float, nullable=True)
    error_type = Column(String(128), nullable=True)
    error_message = Column(Text, nullable=True)
    trace_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)

    run = relationship("EvaluationRun", back_populates="results")


class EvaluationMetric(Base):
    __tablename__ = "evaluation_metrics"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(64), ForeignKey("evaluation_runs.run_id", ondelete="CASCADE"), nullable=False, index=True)
    metric_name = Column(String(64), nullable=False, index=True)
    metric_value = Column(Float, nullable=True)
    denominator = Column(Float, nullable=True)
    numerator = Column(Float, nullable=True)
    metric_status = Column(String(32), default="AVAILABLE", nullable=False)  # AVAILABLE, METRIC_UNAVAILABLE, INSUFFICIENT_DATA
    metric_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=utcnow_naive, nullable=False)

    run = relationship("EvaluationRun", back_populates="metrics")
