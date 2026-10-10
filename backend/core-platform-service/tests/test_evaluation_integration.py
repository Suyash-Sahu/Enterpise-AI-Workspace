import os
import shutil
import uuid
from unittest.mock import patch
import pytest
from app.db.session import SessionLocal
from app.evaluation.runner import EvaluationRunner
from app.evaluation.schemas import EvaluationConfigSchema, EvaluationResultItemSchema
from app.models.evaluation import EvaluationRun, EvaluationTask, EvaluationResult, EvaluationMetric

# Regression (Phase 10 data-integrity audit): this test's mock previously ran
# against a fresh auto-generated run_id with no cleanup at all. Tests here
# share the REAL database (see tests/conftest.py), not an isolated test DB,
# so every pytest run silently inserted a "completed" EvaluationRun row with
# fabricated, identical-across-tasks data (task_id="task_001", latency_ms=
# 120.0, actual_model="ollama/qwen2.5-coder", ...) into the same tables the
# research evaluation pipeline and paper draw evidence from -- indistinguish-
# able from a real run except for those suspiciously-round values. Two such
# rows (run_d1c473acb6bb, run_f34f80ed4275) were found and traced directly
# back to this test. Fix: use a caller-supplied, clearly test-namespaced
# run_id, and purge every row for it in a `finally` block that runs whether
# the test passes, fails an assertion, or raises -- verified by a dedicated
# regression test below that this cleanup survives a mid-test failure.

_MOCK_RESULT_KWARGS = dict(
    task_id="task_001",
    task_text="Test prompt",
    category="document_summary",
    complexity="simple",
    privacy_level="internal",
    expected_capability="document_summary",
    expected_execution_mode="local",
    actual_capability="document_summary",
    actual_execution_mode="local",
    actual_model="ollama/qwen2.5-coder",
    routing_correct=True,
    capability_correct=True,
    completion_success=True,
    latency_ms=120.0,
    input_tokens=100,
    output_tokens=50,
    total_tokens=150,
    estimated_cost=0.0,
    privacy_classification="internal",
    privacy_confidence=0.87,
)


def _new_test_run_id() -> str:
    # "run_test_fixture_" makes this unmistakable as mocked/synthetic data
    # even if cleanup somehow failed and someone later inspected the table
    # directly -- a real run's id is just "run_<hex>".
    return f"run_test_fixture_{uuid.uuid4().hex[:12]}"


def _purge_evaluation_run(db, run_id: str) -> None:
    """
    Deletes every row this test (or a failed prior run of it) could have
    written for run_id, and the filesystem artifact directory start_run()
    unconditionally writes via save_artifacts() (evaluation/artifacts/<run_id>/
    -- found still contaminated with 14 leftover run_test_fixture_* directories
    even after the DB-row cleanup above was added, since that cleanup never
    touched the filesystem). Explicit per-table deletes rather than relying on
    ORM/DB cascade being correctly wired -- this is the one thing standing
    between a mocked unit test and silently contaminating the same database
    (and artifact directory) the research pipeline reads from.
    """
    db.query(EvaluationResult).filter(EvaluationResult.run_id == run_id).delete()
    db.query(EvaluationTask).filter(EvaluationTask.run_id == run_id).delete()
    db.query(EvaluationMetric).filter(EvaluationMetric.run_id == run_id).delete()
    db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).delete()
    db.commit()

    run_dir = os.path.join(EvaluationRunner.ARTIFACTS_DIR, run_id)
    shutil.rmtree(run_dir, ignore_errors=True)


def test_evaluation_runner_integration():
    """
    Verifies EvaluationRunner.start_run's orchestration (task loop, metrics,
    run-status update) without a real LLM call, by mocking TaskExecutor at
    the boundary -- and cleans up the row it necessarily writes to the
    shared database regardless of outcome.
    """
    db = SessionLocal()
    test_run_id = _new_test_run_id()
    try:
        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        mock_result = EvaluationResultItemSchema(**_MOCK_RESULT_KWARGS)

        with patch("app.evaluation.runner.TaskExecutor.execute_task", return_value=mock_result):
            res = EvaluationRunner.start_run(
                db=db,
                dataset_version="amof_eval_v1",
                config=config,
                run_baselines=False,
                run_ablations=False,
                existing_run_id=test_run_id,
            )
            assert res.run_id == test_run_id
            assert res.status in {"completed", "failed"}
            assert res.task_count > 0
            assert len(res.metrics) > 0
    finally:
        _purge_evaluation_run(db, test_run_id)
        db.close()


def test_evaluation_runner_integration_cleans_up_even_on_failure():
    """
    Regression guard for the cleanup mechanism itself, not for the runner:
    even when the test body raises partway through (a failed assertion, or
    an exception from start_run), the run_id it used must not survive in the
    database afterward. This is what actually prevents recurrence of the
    task_001 contamination -- a cleanup that only ran on the happy path
    would not have caught it, since the original bug was never about the
    test failing.
    """
    db = SessionLocal()
    test_run_id = _new_test_run_id()
    try:
        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        mock_result = EvaluationResultItemSchema(**_MOCK_RESULT_KWARGS)

        with patch("app.evaluation.runner.TaskExecutor.execute_task", return_value=mock_result):
            EvaluationRunner.start_run(
                db=db,
                dataset_version="amof_eval_v1",
                config=config,
                run_baselines=False,
                run_ablations=False,
                existing_run_id=test_run_id,
            )
            raise RuntimeError("simulated assertion failure inside the test body")
    except RuntimeError:
        pass
    finally:
        _purge_evaluation_run(db, test_run_id)
        db.close()

    verify_db = SessionLocal()
    try:
        assert verify_db.query(EvaluationRun).filter(EvaluationRun.run_id == test_run_id).first() is None
        assert verify_db.query(EvaluationResult).filter(EvaluationResult.run_id == test_run_id).count() == 0
        assert verify_db.query(EvaluationTask).filter(EvaluationTask.run_id == test_run_id).count() == 0
        assert verify_db.query(EvaluationMetric).filter(EvaluationMetric.run_id == test_run_id).count() == 0
    finally:
        verify_db.close()


def test_no_leftover_fixture_runs_in_database():
    """
    Direct regression check for the actual historical contamination: no
    run_id in the database should ever be a "run_test_fixture_*" id (this
    test's own namespace) still present after the suite runs, and no run
    should carry the exact fabricated signature that identified the
    original bug (task_id="task_001" repeated as the ONLY task_id across
    all of a run's results, paired with the literal schema-default model
    name "ollama/qwen2.5-coder" and latency_ms=120.0 on every row).
    """
    db = SessionLocal()
    try:
        leftover_fixtures = (
            db.query(EvaluationRun)
            .filter(EvaluationRun.run_id.like("run_test_fixture_%"))
            .all()
        )
        assert leftover_fixtures == [], (
            f"Found {len(leftover_fixtures)} uncleaned test-fixture run(s) in the "
            "database -- a prior test run's cleanup failed: "
            f"{[r.run_id for r in leftover_fixtures]}"
        )
    finally:
        db.close()


def test_no_leftover_fixture_artifacts_on_disk():
    """
    Filesystem counterpart to test_no_leftover_fixture_runs_in_database:
    start_run() unconditionally writes evaluation/artifacts/<run_id>/ via
    save_artifacts(), a side effect independent of the database rows the
    DB-cleanup test checks. 14 such directories (run_test_fixture_*) were
    found still on disk during the Phase 10 token audit (2026-09-20) even
    after DB-row cleanup was already in place -- this is what would have
    caught that.
    """
    if not os.path.isdir(EvaluationRunner.ARTIFACTS_DIR):
        return
    leftover_dirs = [
        name
        for name in os.listdir(EvaluationRunner.ARTIFACTS_DIR)
        if name.startswith("run_test_fixture_")
    ]
    assert leftover_dirs == [], (
        f"Found {len(leftover_dirs)} uncleaned test-fixture artifact "
        f"director(y/ies) on disk -- a prior test run's cleanup failed: {leftover_dirs}"
    )


def test_evaluation_artifacts_include_nonempty_csv_with_privacy_confidence():
    """
    Regression (smoke-eval data-integrity audit, 2026-09-20):
    evaluation_results.csv was never generated for ANY run since
    privacy_confidence was added to EvaluationResultItemSchema (~2026-09-12),
    because EvaluationExporter.export_csv reads r.privacy_confidence off the
    EvaluationResult DB row, but that column never existed on the model --
    every call crashed with AttributeError, and the crash was silently
    swallowed by runner.py's save_artifacts() try/except (see the failure-not-
    swallowed test below). Fixed: the column now exists (migration
    4dbe0d7d0a10) and is wired through save_result(). This proves the CSV
    is actually written, non-empty, and carries the real value through.
    """
    import csv

    db = SessionLocal()
    test_run_id = _new_test_run_id()
    try:
        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        mock_result = EvaluationResultItemSchema(**_MOCK_RESULT_KWARGS)

        with patch("app.evaluation.runner.TaskExecutor.execute_task", return_value=mock_result):
            res = EvaluationRunner.start_run(
                db=db,
                dataset_version="amof_eval_v1",
                config=config,
                run_baselines=False,
                run_ablations=False,
                existing_run_id=test_run_id,
            )

        assert res.artifact_error is None, f"artifact generation failed: {res.artifact_error}"

        csv_path = os.path.join(EvaluationRunner.ARTIFACTS_DIR, test_run_id, "evaluation_results.csv")
        assert os.path.isfile(csv_path), "evaluation_results.csv was not written"
        assert os.path.getsize(csv_path) > 0, "evaluation_results.csv is empty"

        with open(csv_path, "r", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0
        row = next(r for r in rows if r["task_id"] == "task_001")
        assert row["privacy_confidence"] == "0.87"
        assert row["capability_correct"] == "True"
    finally:
        _purge_evaluation_run(db, test_run_id)
        db.close()


def test_evaluation_artifact_failure_is_recorded_not_swallowed():
    """
    Regression: save_artifacts() failures used to be logged (str(e), no
    traceback) and otherwise disappear -- the run still reported "completed"
    with no way to tell its artifacts were missing/incomplete short of
    manually checking the filesystem. Now the failure must be visible on
    both EvaluationRun.artifact_error (DB) and the response schema.
    """
    db = SessionLocal()
    test_run_id = _new_test_run_id()
    try:
        config = EvaluationConfigSchema(dataset_version="amof_eval_v1")
        mock_result = EvaluationResultItemSchema(**_MOCK_RESULT_KWARGS)

        with patch("app.evaluation.runner.TaskExecutor.execute_task", return_value=mock_result), patch(
            "app.evaluation.runner.EvaluationExporter.export_csv",
            side_effect=RuntimeError("simulated export failure"),
        ):
            res = EvaluationRunner.start_run(
                db=db,
                dataset_version="amof_eval_v1",
                config=config,
                run_baselines=False,
                run_ablations=False,
                existing_run_id=test_run_id,
            )

        # The evaluation itself must still succeed -- an artifact-export bug
        # must never take down data collection that already happened.
        assert res.status == "completed"
        assert res.artifact_error is not None
        assert "simulated export failure" in res.artifact_error

        verify_db = SessionLocal()
        try:
            run_row = verify_db.query(EvaluationRun).filter(EvaluationRun.run_id == test_run_id).first()
            assert run_row.artifact_error is not None
            assert "simulated export failure" in run_row.artifact_error
        finally:
            verify_db.close()
    finally:
        _purge_evaluation_run(db, test_run_id)
        db.close()

