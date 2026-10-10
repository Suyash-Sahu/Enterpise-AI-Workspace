import pytest
from app.evaluation.baselines import BaselineRunner


def test_baseline_runner_constants():
    assert "ALWAYS_LOCAL" in BaselineRunner.BASELINES
    assert "ALWAYS_CLOUD" in BaselineRunner.BASELINES
    assert "STATIC_RULE" in BaselineRunner.BASELINES
    assert "AMOF" in BaselineRunner.BASELINES
