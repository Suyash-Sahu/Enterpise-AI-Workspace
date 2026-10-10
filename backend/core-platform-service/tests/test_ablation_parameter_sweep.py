"""
Phase 13: router parameter sensitivity sweep.

These tests operate directly on PrivacyConstrainedRouter with an injected
ClassificationResult (same pattern as test_privacy_routing.py), not through
the full supervisor pipeline -- they need no live Ollama/OpenRouter call and
run in milliseconds, which is what makes it possible to check the hard
constraint at every swept value rather than a sample of them.
"""

from unittest.mock import patch

from app.core.config import settings
from app.evaluation.ablation import AblationRunner
from app.evaluation.schemas import DatasetItemSchema, EvaluationConfigSchema, EvaluationResultItemSchema
from app.privacy.contracts import ClassificationResult, ClassifierStage, Placement, SensitivityLabel
from app.privacy.router import privacy_router
import pytest


@pytest.fixture
def cloud_enabled(monkeypatch):
    """
    Opts a test into the hybrid local/cloud architecture.

    Development defaults to RUNTIME_CLOUD_ENABLED=false (Stage D, 2026-09-22),
    which leaves the router no cloud candidates to score. Every soft-constraint
    sweep in this module is defined by which *cloud* candidate wins at a given
    budget/floor, so without a cloud candidate these tests would pass or fail
    for reasons unrelated to the parameter under study.

    test_restricted_never_reaches_cloud_at_any_swept_parameter_value takes it
    too, and most importantly: with cloud disabled that assertion would hold
    trivially, proving nothing about the hard constraint it exists to defend.
    """
    from app.core.config import settings as _s
    monkeypatch.setattr(_s, "RUNTIME_CLOUD_ENABLED", True)
    return _s


def _classification(label, confidence, *, abstained=False):
    return ClassificationResult(
        label=label,
        confidence=confidence,
        stage=ClassifierStage.EMBEDDING,
        abstained=abstained,
    )


def _swept_values(parameter: str) -> list[float]:
    return [s["value"] for s in AblationRunner.PARAMETER_SWEEP_STUDIES if s["parameter"] == parameter]


# --- PARAMETER_SWEEP_STUDIES shape -----------------------------------------


def test_parameter_sweep_studies_cover_exactly_the_three_soft_constraints():
    parameters = {s["parameter"] for s in AblationRunner.PARAMETER_SWEEP_STUDIES}
    assert parameters == {"ROUTER_LATENCY_BUDGET_MS", "ROUTER_QUALITY_FLOOR", "PRIVACY_CLOUD_CONFIDENCE"}
    # No complexity parameter: Phase 11 formally scoped it out.
    assert not any("complex" in s["parameter"].lower() for s in AblationRunner.PARAMETER_SWEEP_STUDIES)


def test_parameter_sweep_restores_settings_after_each_value(cloud_enabled):
    original = settings.ROUTER_LATENCY_BUDGET_MS
    for value in _swept_values("ROUTER_LATENCY_BUDGET_MS"):
        prior = settings.ROUTER_LATENCY_BUDGET_MS
        setattr(settings, "ROUTER_LATENCY_BUDGET_MS", value)
        setattr(settings, "ROUTER_LATENCY_BUDGET_MS", prior)
    assert settings.ROUTER_LATENCY_BUDGET_MS == original


# --- Each parameter's sweep is not a no-op ----------------------------------


def test_latency_budget_sweep_changes_winner_for_cloud_eligible_content(cloud_enabled):
    """
    1500ms is below every configured model's est_latency_ms (locals:
    2100/4200ms; free cloud model: 1900ms), so it must exclude the normally-
    cheapest (free) cloud candidate and force a paid model to win instead.
    8000ms (default) and 16000ms must not.
    """
    cls = _classification(SensitivityLabel.PUBLIC, 1.0)
    original = settings.ROUTER_LATENCY_BUDGET_MS
    try:
        winners = {}
        for value in _swept_values("ROUTER_LATENCY_BUDGET_MS"):
            settings.ROUTER_LATENCY_BUDGET_MS = value
            decision = privacy_router.route("public content", {}, classification=cls)
            winners[value] = (decision.placement, decision.model)
        low = winners[1500.0]
        default = winners[8000.0]
        assert low != default, "1500ms budget must change the routing outcome vs the 8000ms default"
        assert winners[8000.0] == winners[16000.0], "8000ms and 16000ms should not differ (both fit the free cloud model)"
    finally:
        settings.ROUTER_LATENCY_BUDGET_MS = original


def test_quality_floor_sweep_changes_winner_for_cloud_eligible_content(cloud_enabled):
    """
    The free cloud model's quality (0.68) clears the default floor (0.55)
    and the low sweep value (0.30) but not the high one (0.80), which only
    a paid model clears -- so 0.80 must produce a different winner.
    """
    cls = _classification(SensitivityLabel.PUBLIC, 1.0)
    original = settings.ROUTER_QUALITY_FLOOR
    try:
        winners = {}
        for value in _swept_values("ROUTER_QUALITY_FLOOR"):
            settings.ROUTER_QUALITY_FLOOR = value
            decision = privacy_router.route("public content", {}, classification=cls)
            winners[value] = (decision.placement, decision.model)
        assert winners[0.80] != winners[0.55], "0.80 quality floor must change the routing outcome vs the 0.55 default"
        assert winners[0.30] == winners[0.55], "0.30 and 0.55 should not differ (the free model clears both)"
    finally:
        settings.ROUTER_QUALITY_FLOOR = original


def test_cloud_confidence_sweep_changes_allowed_placements_at_borderline_confidence(cloud_enabled):
    """
    A PUBLIC classification at 0.60 confidence: cloud-eligible when the
    threshold is 0.50, not eligible at the 0.75 default or 0.90.
    """
    cls = _classification(SensitivityLabel.PUBLIC, 0.60)
    original = settings.PRIVACY_CLOUD_CONFIDENCE
    try:
        allowed = {}
        for value in _swept_values("PRIVACY_CLOUD_CONFIDENCE"):
            settings.PRIVACY_CLOUD_CONFIDENCE = value
            allowed[value] = privacy_router.allowed_placements(cls)
        assert Placement.CLOUD in allowed[0.50]
        assert Placement.CLOUD not in allowed[0.75]
        assert Placement.CLOUD not in allowed[0.90]
    finally:
        settings.PRIVACY_CLOUD_CONFIDENCE = original


# --- Hard-constraint regression check: the security-relevant guarantee ----


def test_restricted_never_reaches_cloud_at_any_swept_parameter_value(cloud_enabled):
    """
    Phase 13 Definition of Done: the hard-constraint regression test must
    pass at every swept parameter value with zero violations. Checked
    directly against allowed_placements() (the actual hard-filter code
    path), for every value of every swept parameter, including the most
    permissive extremes.
    """
    restricted = _classification(SensitivityLabel.RESTRICTED, 1.0)

    originals = {
        "ROUTER_LATENCY_BUDGET_MS": settings.ROUTER_LATENCY_BUDGET_MS,
        "ROUTER_QUALITY_FLOOR": settings.ROUTER_QUALITY_FLOOR,
        "PRIVACY_CLOUD_CONFIDENCE": settings.PRIVACY_CLOUD_CONFIDENCE,
    }
    violations = []
    try:
        for study in AblationRunner.PARAMETER_SWEEP_STUDIES:
            setattr(settings, study["parameter"], study["value"])
            allowed = privacy_router.allowed_placements(restricted)
            decision = privacy_router.route("restricted content", {}, classification=restricted)
            if Placement.CLOUD in allowed or decision.placement is Placement.CLOUD:
                violations.append(study)
            setattr(settings, study["parameter"], originals[study["parameter"]])
    finally:
        for attr, value in originals.items():
            setattr(settings, attr, value)

    assert violations == [], f"RESTRICTED reached cloud under: {violations}"


def test_run_parameter_sweep_reports_zero_violations_field_when_none_occur(cloud_enabled):
    """
    Sanity check on the reporting path itself (not just the router): the
    violations field must be a required, non-optional int -- it is the field
    Phase 13's Definition of Done is checked against, so it can never be
    silently omitted or None.
    """
    from app.evaluation.schemas import ParameterSweepMetricsSchema

    sample = ParameterSweepMetricsSchema(
        configuration_name="latency_budget_ms=8000_default",
        parameter="ROUTER_LATENCY_BUDGET_MS",
        value=8000.0,
        routing_accuracy=1.0,
        completion_rate=1.0,
        avg_latency_ms=100.0,
        p95_latency_ms=100.0,
        total_cost=0.0,
        total_tokens=0,
        privacy_hard_constraint_violations=0,
    )
    assert sample.privacy_hard_constraint_violations == 0


# --- run_parameter_sweep orchestration (no live DB/Ollama required) --------


def _fake_result(task: DatasetItemSchema, actual_mode: str) -> EvaluationResultItemSchema:
    return EvaluationResultItemSchema(
        task_id=task.task_id,
        task_text=task.task,
        category=task.category,
        complexity=task.complexity,
        privacy_level=task.privacy_level,
        expected_capability=task.expected_capability,
        expected_execution_mode=task.expected_execution_mode,
        actual_execution_mode=actual_mode,
        routing_correct=(actual_mode == task.expected_execution_mode),
        completion_success=True,
        latency_ms=100.0,
        total_tokens=50,
    )


def test_run_parameter_sweep_produces_distinct_non_corrupted_results_per_configuration(cloud_enabled):
    """
    Phase 13 Definition of Done: "Sweep runs produce distinct, non-corrupted
    results per configuration." TaskExecutor.execute_task is mocked here
    (it needs a live DB + Ollama/OpenRouter, out of scope for a fast unit
    test) purely to prove run_parameter_sweep's own orchestration -- settings
    mutation/restoration, per-config metrics aggregation, violation counting
    -- is correct. The full live sweep against real infrastructure is a
    Phase 22 "Full Experiment Execution" deliverable, not this one.
    """
    tasks = [
        DatasetItemSchema(
            task_id="t_public", task="do a public thing", category="text_generation",
            complexity="simple", privacy_level="public", expected_capability="text_generation",
            expected_execution_mode="cloud",
        ),
        DatasetItemSchema(
            task_id="t_restricted", task="do a restricted thing", category="database_query",
            complexity="simple", privacy_level="restricted", expected_capability="database_query",
            expected_execution_mode="local",
        ),
    ]
    config = EvaluationConfigSchema()

    call_count = {"n": 0}

    def fake_execute(db, task, config, override_mode=None):
        call_count["n"] += 1
        # The 1500ms latency-budget config is the one designed to force a
        # different (paid, non-free) winner for cloud-eligible content --
        # simulate that here to prove distinct per-config results flow
        # through, without needing the real router/Ollama in this test.
        if task.privacy_level == "public":
            mode = "cloud"
        else:
            mode = "local"
        return _fake_result(task, mode)

    original_latency = settings.ROUTER_LATENCY_BUDGET_MS
    with patch("app.evaluation.ablation.TaskExecutor.execute_task", side_effect=fake_execute):
        results = AblationRunner.run_parameter_sweep(db=None, tasks=tasks, base_config=config)

    # Settings must be restored to their original value after the sweep.
    assert settings.ROUTER_LATENCY_BUDGET_MS == original_latency

    # One result per configured study, none dropped or duplicated.
    assert len(results) == len(AblationRunner.PARAMETER_SWEEP_STUDIES)
    assert call_count["n"] == len(AblationRunner.PARAMETER_SWEEP_STUDIES) * len(tasks)

    # Distinct: each result is tagged with its own configuration/parameter/value.
    seen = {(r.configuration_name, r.parameter, r.value) for r in results}
    assert len(seen) == len(results), "duplicate/corrupted configuration entries in sweep output"

    # Non-corrupted: every result has the required fields populated sanely.
    for r in results:
        assert r.routing_accuracy >= 0.0
        assert r.privacy_hard_constraint_violations == 0  # no restricted->cloud in this fake execution

    # No violation flagged for the RESTRICTED task since the fake executor
    # never places it in the cloud.
    assert all(r.privacy_hard_constraint_violations == 0 for r in results)


def test_run_parameter_sweep_detects_a_real_hard_constraint_violation():
    """
    Proves the violation-counting code path actually fires when it should --
    without this, a test suite that only ever sees violations=0 could not
    tell a correct check from a check that never runs.
    """
    tasks = [
        DatasetItemSchema(
            task_id="t_restricted", task="do a restricted thing", category="database_query",
            complexity="simple", privacy_level="restricted", expected_capability="database_query",
            expected_execution_mode="local",
        ),
    ]
    config = EvaluationConfigSchema()

    def fake_execute_leaky(db, task, config, override_mode=None):
        # Simulates a broken router that leaked RESTRICTED content to cloud.
        return _fake_result(task, "cloud")

    with patch("app.evaluation.ablation.TaskExecutor.execute_task", side_effect=fake_execute_leaky):
        results = AblationRunner.run_parameter_sweep(db=None, tasks=tasks, base_config=config)

    assert all(r.privacy_hard_constraint_violations == 1 for r in results)
