"""
Regression tests (Phase 10 data-integrity audit): TaskExecutor.execute_task
must report the routing DECISION (what mode was actually dispatched)
independently of the execution OUTCOME (whether it then succeeded).

Two scenarios were directly diagnosed against the real code before this fix:

1. A real Execution row exists with execution_mode="cloud" and status=
   "FAILED" (e.g. RuntimePolicyError, ProviderUnavailableError, or an
   OpenRouter 429). This ALREADY worked correctly before this change --
   actual_execution_mode/cloud_execution correctly reflected "cloud" with
   completion_success=False. Locked in here so it can't regress.

2. amof_supervisor.run() raises before any step is ever dispatched (no
   Execution row exists at all -- e.g. an intent-classification-level
   crash). This previously defaulted actual_execution_mode to the literal
   string "local" (and cloud_execution to False), indistinguishable from a
   genuine successful local execution. Fixed: these now stay None
   ("unknown / nothing dispatched") rather than a guessed "local".
"""
import json
import uuid
from unittest.mock import patch

from app.db.database import Base, engine
from app.db.session import SessionLocal
from app.evaluation.executor import TaskExecutor
from app.evaluation.schemas import DatasetItemSchema, EvaluationConfigSchema
from app.models.execution import Execution
from app.schemas.execution import ExecutionStatus
from app.schemas.supervisor import IntentResult, SupervisorResponse
from app.utils.timeutils import utcnow_naive


def _task(task_id: str) -> DatasetItemSchema:
    return DatasetItemSchema(
        task_id=task_id,
        task="diagnostic task",
        category="text_generation",
        complexity="medium",
        privacy_level="internal",
        expected_capability="text_generation",
        expected_execution_mode="cloud",
        expected_approval_requirement=False,
    )


def test_failed_cloud_execution_is_reported_as_cloud_not_local():
    """
    A dispatched-but-failed cloud attempt must be recorded as
    actual_execution_mode="cloud", cloud_execution=True,
    completion_success=False -- never silently downgraded to "local".
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    exec_id = str(uuid.uuid4())
    try:
        rec = Execution(
            id=exec_id,
            owner_id="1",
            task_type="text_generation",
            status=ExecutionStatus.FAILED.value,
            execution_mode="cloud",
            provider=None,
            model=None,
            result_json=None,
            error_type="RuntimePolicyError",
            error_message="Cloud execution refused: content classified 'internal'",
            execution_time=0.5,
            retry_count=0,
            created_at=utcnow_naive(),
        )
        db.add(rec)
        db.commit()

        fake_response = SupervisorResponse(
            request_id="test-req",
            trace_id="test-trace",
            status="FAILED",
            intent=IntentResult(capability="text_generation", confidence=0.9, reason="test"),
            answer="",
            sources=[],
            execution_ids=[exec_id],
            steps=[],
            execution_time=0.5,
        )

        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        with patch("app.evaluation.executor.amof_supervisor.run", return_value=fake_response):
            res = TaskExecutor.execute_task(db=db, task=_task("diag_cloud_failed"), config=config)

        assert res.actual_execution_mode == "cloud"
        assert res.cloud_execution is True
        assert res.completion_success is False
        assert res.actual_model == config.cloud_model
    finally:
        db.query(Execution).filter(Execution.id == exec_id).delete()
        db.commit()
        db.close()


def test_crash_before_any_dispatch_reports_unknown_not_local():
    """
    When the supervisor raises before ever dispatching a step -- no
    Execution row exists to inspect at all -- the mode must be reported as
    unknown (None), not silently defaulted to "local".
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        with patch(
            "app.evaluation.executor.amof_supervisor.run",
            side_effect=RuntimeError("simulated total supervisor crash before any dispatch"),
        ):
            res = TaskExecutor.execute_task(db=db, task=_task("diag_no_dispatch"), config=config)

        assert res.actual_execution_mode is None
        assert res.cloud_execution is None
        assert res.actual_model is None
        assert res.completion_success is False
        assert res.error_type == "RuntimeError"
    finally:
        db.close()


def test_successful_local_execution_still_reports_local():
    """
    Guards against over-correcting: a genuinely local, successfully
    completed execution must still be reported as actual_execution_mode=
    "local", not None -- "unknown" only applies when nothing was dispatched.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    exec_id = str(uuid.uuid4())
    try:
        rec = Execution(
            id=exec_id,
            owner_id="1",
            task_type="text_generation",
            status=ExecutionStatus.COMPLETED.value,
            execution_mode="local",
            provider="ollama",
            model="qwen2.5:3b-instruct",
            result_json=json.dumps({"tokens": {"input": 42, "output": 17}}),
            execution_time=1.2,
            retry_count=0,
            created_at=utcnow_naive(),
        )
        db.add(rec)
        db.commit()

        fake_response = SupervisorResponse(
            request_id="test-req",
            trace_id="test-trace",
            status="COMPLETED",
            intent=IntentResult(capability="text_generation", confidence=0.95, reason="test"),
            answer="a real answer",
            sources=[],
            execution_ids=[exec_id],
            steps=[],
            execution_time=1.2,
        )

        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        with patch("app.evaluation.executor.amof_supervisor.run", return_value=fake_response), \
             patch("app.evaluation.executor.quality_judge.judge", return_value=type("J", (), {"overall": 0.8})()):
            res = TaskExecutor.execute_task(db=db, task=_task("diag_local_ok"), config=config)

        assert res.actual_execution_mode == "local"
        assert res.cloud_execution is False
        # The real dispatched model (from the Execution row), not the
        # EvaluationConfigSchema placeholder default -- reproducibility
        # requires recording what actually ran.
        assert res.actual_model == "qwen2.5:3b-instruct"
        assert res.input_tokens == 42
        assert res.output_tokens == 17
        assert res.total_tokens == 59
    finally:
        db.query(Execution).filter(Execution.id == exec_id).delete()
        db.commit()
        db.close()


def test_capability_correct_is_independent_of_routing_correct():
    """
    Regression (smoke evaluation, 2026-09-20): a rag_answer task whose intent
    was misclassified as database_query still landed on "cloud" placement
    (matching expected_execution_mode), so routing_correct=True hid a
    completely wrong capability choice -- routing_correct only ever measures
    local/cloud placement (app/evaluation/executor.py), never capability.
    capability_correct is the separate, independent field that must catch
    this: True capability match required, regardless of whether placement
    happened to be correct too.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    exec_id = str(uuid.uuid4())
    try:
        rec = Execution(
            id=exec_id,
            owner_id="1",
            task_type="database_query",
            status=ExecutionStatus.COMPLETED.value,
            execution_mode="cloud",
            provider="litellm/openrouter",
            model="openai/gpt-4o-mini",
            result_json=json.dumps({}),
            execution_time=0.8,
            retry_count=0,
            created_at=utcnow_naive(),
        )
        db.add(rec)
        db.commit()

        # _task()'s expected_capability is "text_generation" and
        # expected_execution_mode is "cloud" -- the intent below is
        # deliberately the WRONG capability ("database_query") while the
        # dispatched placement still matches expected_execution_mode.
        fake_response = SupervisorResponse(
            request_id="test-req",
            trace_id="test-trace",
            status="COMPLETED",
            intent=IntentResult(capability="database_query", confidence=0.9, reason="test"),
            answer="an answer from the wrong capability",
            sources=[],
            execution_ids=[exec_id],
            steps=[],
            execution_time=0.8,
        )

        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        with patch("app.evaluation.executor.amof_supervisor.run", return_value=fake_response), \
             patch("app.evaluation.executor.quality_judge.judge", return_value=type("J", (), {"overall": 0.5})()):
            res = TaskExecutor.execute_task(db=db, task=_task("diag_capability_mismatch"), config=config)

        assert res.actual_capability == "database_query"
        assert res.actual_execution_mode == "cloud"
        assert res.routing_correct is True, "placement matched expected_execution_mode"
        assert res.capability_correct is False, "capability did not match expected_capability"
    finally:
        db.query(Execution).filter(Execution.id == exec_id).delete()
        db.commit()
        db.close()
