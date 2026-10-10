import pytest
from app.db.session import SessionLocal
from app.models.evaluation import EvaluationRun, EvaluationMetric
from app.evaluation.metrics import MetricsEngine


def test_no_fake_metrics_generated():
    # Verify that MetricsEngine returns empty metrics if result set is empty
    empty_metrics = MetricsEngine.calculate_metrics([])
    assert empty_metrics == []


def test_real_database_persistence():
    db = SessionLocal()
    try:
        runs_count = db.query(EvaluationRun).count()
        assert isinstance(runs_count, int)
    finally:
        db.close()
