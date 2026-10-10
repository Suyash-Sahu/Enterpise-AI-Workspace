"""
Phase 14: chart generation tests.

Reuses the exact test-run-id-namespacing and cleanup pattern from
test_evaluation_integration.py (see its own comment on why: this suite
shares the real database with the research pipeline, and an uncleaned test
row is indistinguishable from real evaluation data except by its run_id
prefix). Chart files are written under the real ARTIFACTS_DIR too, using a
run_test_fixture_* run_id, and are removed in the same cleanup as the DB rows.
"""

import os
from unittest.mock import patch

from app.db.session import SessionLocal
from app.evaluation.exporters import EvaluationExporter
from app.evaluation.runner import EvaluationRunner
from app.evaluation.schemas import EvaluationConfigSchema, EvaluationResultItemSchema
from tests.test_evaluation_integration import (
    _MOCK_RESULT_KWARGS,
    _new_test_run_id,
    _purge_evaluation_run,
)


def test_export_charts_produces_real_files_from_a_real_run():
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
        assert res.status in {"completed", "failed"}

        charts_dir = os.path.join(EvaluationRunner.ARTIFACTS_DIR, test_run_id, "test_charts")
        charts = EvaluationExporter.export_charts(db=db, run_id=test_run_id, output_dir=charts_dir)

        # This run has metrics and per-task latency (the mocked result sets
        # latency_ms=120.0), so those two charts must exist as real files.
        assert "metrics_summary" in charts
        assert "latency_distribution" in charts
        for path in charts.values():
            assert os.path.isfile(path)
            assert os.path.getsize(path) > 0

        # No baselines were run (run_baselines=False) -- that chart must be
        # omitted, not rendered empty.
        assert "baseline_comparison" not in charts
    finally:
        _purge_evaluation_run(db, test_run_id)
        db.close()


def test_export_charts_returns_empty_dict_for_a_run_with_no_data():
    """A run_id with nothing persisted must produce no charts, not empty/corrupt files."""
    db = SessionLocal()
    charts_dir = os.path.join(EvaluationRunner.ARTIFACTS_DIR, "run_test_fixture_nonexistent", "charts")
    try:
        charts = EvaluationExporter.export_charts(db=db, run_id="run_test_fixture_nonexistent_00000", output_dir=charts_dir)
        assert charts == {}
        assert not os.path.exists(charts_dir) or os.listdir(charts_dir) == []
    finally:
        db.close()
        import shutil
        shutil.rmtree(os.path.join(EvaluationRunner.ARTIFACTS_DIR, "run_test_fixture_nonexistent"), ignore_errors=True)
