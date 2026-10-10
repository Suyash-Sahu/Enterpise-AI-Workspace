"""
Tests for the privacy-constrained router, its classifier, and the verifier.

The load-bearing tests are the ones asserting what must NEVER happen:
sensitive content reaching a cloud placement, an abstention resolving to
anything other than local, and a cost advantage overriding the constraint.
"""

import pytest

from app.privacy.classifier import privacy_classifier
from app.privacy.contracts import (
    ClassificationResult,
    ClassifierStage,
    Placement,
    SensitivityLabel,
)
from app.privacy.patterns import luhn_valid, scan, verhoeff_valid
from app.privacy.router import privacy_router
from app.supervisor.verifier import response_verifier


@pytest.fixture
def cloud_enabled(monkeypatch):
    """
    Opts a test into the hybrid local/cloud architecture.

    Development defaults to RUNTIME_CLOUD_ENABLED=false (Stage D, 2026-09-22),
    which empties the cloud half of the router's candidate set so every request
    resolves local against Ollama. The privacy constraint itself is untouched by
    that switch, but a test asserting that PUBLIC content *reaches* cloud needs a
    cloud candidate to exist at all, so it must ask for one explicitly.

    The refusal tests (test_decision_audit_records_why_cloud_was_refused,
    test_explicitly_requested_cloud_is_refused_for_sensitive_content) take this
    fixture for the opposite reason: with cloud switched off, "cloud was
    refused" would pass vacuously, proving only that the dev switch works.
    Enabling cloud first is what makes their pass attributable to the privacy
    constraint.
    """
    from app.core.config import settings
    monkeypatch.setattr(settings, "RUNTIME_CLOUD_ENABLED", True)
    return settings


def _classification(label, confidence, *, abstained=False):
    return ClassificationResult(
        label=label,
        confidence=confidence,
        stage=ClassifierStage.EMBEDDING,
        abstained=abstained,
    )


# --- Detector precision -----------------------------------------------------


def test_luhn_accepts_real_card_and_rejects_lookalike():
    assert luhn_valid("4111 1111 1111 1111")
    # A 16-digit order number that is not a card must not fire, or every
    # invoice id in the corpus would be classified confidential.
    assert not luhn_valid("1234567890123456")


def test_verhoeff_rejects_plain_twelve_digit_numbers():
    assert not verhoeff_valid("123456789012")
    assert not verhoeff_valid("012345678901")  # Aadhaar never starts 0 or 1


def test_scan_reports_span_but_never_the_matched_secret():
    signals = scan("key AKIAIOSFODNN7EXAMPLE here")
    assert signals, "expected the AWS key detector to fire"
    signal = signals[0]
    assert signal.detector == "aws_access_key"
    # Signals are logged; if they carried the match, the audit trail would
    # itself be a disclosure.
    assert not hasattr(signal, "text")
    assert isinstance(signal.span, tuple)


# --- Classifier -------------------------------------------------------------


def test_escalation_takes_the_most_sensitive_label():
    assert (
        SensitivityLabel.escalate(
            SensitivityLabel.PUBLIC, SensitivityLabel.CONFIDENTIAL
        )
        is SensitivityLabel.CONFIDENTIAL
    )
    # A single strong signal is not diluted by weaker ones.
    assert (
        SensitivityLabel.escalate(
            SensitivityLabel.PUBLIC,
            SensitivityLabel.PUBLIC,
            SensitivityLabel.INTERNAL,
        )
        is SensitivityLabel.INTERNAL
    )


def test_empty_content_fails_closed():
    result = privacy_classifier.classify("")
    assert result.label is SensitivityLabel.CONFIDENTIAL
    assert result.abstained is True


def test_declared_sensitivity_can_raise_but_never_lower():
    text = "Draft release notes for the open source SDK."
    raised = privacy_classifier.classify(
        text, {"declared_sensitivity": "confidential"}
    )
    assert raised.label is SensitivityLabel.CONFIDENTIAL

    # A caller asserting "public" must not be able to talk the classifier down
    # from a detector hit. AWS access keys are RESTRICTED (AMOF-X Phase 3),
    # a strictly higher tier than CONFIDENTIAL -- still not lowerable.
    lowered = privacy_classifier.classify(
        "Rotate key AKIAIOSFODNN7EXAMPLE", {"declared_sensitivity": "public"}
    )
    assert lowered.label is SensitivityLabel.RESTRICTED


@pytest.mark.parametrize(
    "text",
    [
        "Summarize the Q3 payroll and bonus allocation.",
        "Update the record for SSN 078-05-1120.",
        "Charge card 4111 1111 1111 1111.",
    ],
)
def test_sensitive_content_is_classified_confidential(text):
    assert privacy_classifier.classify(text).label is SensitivityLabel.CONFIDENTIAL


@pytest.mark.parametrize(
    "text",
    [
        "-----BEGIN RSA PRIVATE KEY-----",
        "Rotate key AKIAIOSFODNN7EXAMPLE",
        "api_key: sk-abcdefghijklmnopqrstuvwxyz012345",
        "postgres://admin:supersecret@db.internal:5432/prod",
    ],
)
def test_live_credentials_are_classified_restricted(text):
    """
    AMOF-X Phase 3: live credential material is a strictly higher tier than
    CONFIDENTIAL -- leaking one is an ongoing compromise, not just a
    disclosure. See app/privacy/patterns.py's "Secrets and credentials" group.
    """
    result = privacy_classifier.classify(text)
    assert result.label is SensitivityLabel.RESTRICTED
    assert result.label.rank > SensitivityLabel.CONFIDENTIAL.rank


# --- The hard constraint ----------------------------------------------------


@pytest.mark.parametrize(
    "label",
    [SensitivityLabel.INTERNAL, SensitivityLabel.CONFIDENTIAL, SensitivityLabel.RESTRICTED],
)
def test_sensitive_labels_never_reach_cloud(label):
    decision = privacy_router.route(
        "irrelevant", classification=_classification(label, 1.0)
    )
    assert decision.placement is Placement.LOCAL
    assert Placement.CLOUD not in decision.allowed_placements
    assert decision.constraint_binding is True


@pytest.mark.parametrize(
    "confidence,max_cloud_override",
    [
        (1.0, None),
        (0.0, None),
        (1.0, "confidential"),  # the eval harness's unconstrained-baseline escape hatch
        (1.0, "public"),
        (0.0, "confidential"),
    ],
)
def test_restricted_never_reaches_cloud_under_any_scoring_weights(confidence, max_cloud_override):
    """
    AMOF-X Phase 3's hard requirement: RESTRICTED must be provably
    never-cloud-eligible, including under the one override that DOES open
    cloud for every other label (test_eval_override_opens_cloud_for_the_
    unconstrained_baseline, below) -- proven here across confidence levels
    and override values rather than assumed from the CONFIDENTIAL case.
    """
    decision = privacy_router.route(
        "irrelevant",
        classification=_classification(SensitivityLabel.RESTRICTED, confidence),
        max_cloud_label=max_cloud_override,
        est_input_tokens=10_000_000,
        est_output_tokens=10_000_000,  # a huge cost disadvantage for local, same as the existing cost-override test
    )
    assert decision.placement is Placement.LOCAL
    assert Placement.CLOUD not in decision.allowed_placements


def test_restricted_decision_carries_zero_disclosure_risk():
    """Nothing left the machine, so risk is 0 regardless of classifier confidence."""
    decision = privacy_router.route(
        "irrelevant", classification=_classification(SensitivityLabel.RESTRICTED, 0.4)
    )
    assert decision.risk == 0.0


def test_structured_decision_object_populates_new_fields(cloud_enabled):
    """
    AMOF-X Phase 3: the structured decision object -- predicted_quality, risk,
    routing_confidence -- must be populated on every real routing call, not
    left at dataclass defaults.
    """
    decision = privacy_router.route(
        "Write a blog post.",
        classification=_classification(SensitivityLabel.PUBLIC, 0.95),
    )
    assert decision.predicted_quality > 0.0
    assert decision.routing_confidence == 1.0  # no soft constraint relaxed
    assert decision.risk == round(1.0 - 0.95, 4)  # cloud placement: risk tracks classifier uncertainty
    audit = decision.to_audit_dict()
    assert {"predicted_quality", "risk", "routing_confidence"} <= audit.keys()


def test_public_content_with_confidence_reaches_cloud(cloud_enabled):
    decision = privacy_router.route(
        "Write a blog post.",
        classification=_classification(SensitivityLabel.PUBLIC, 0.95),
    )
    assert decision.placement is Placement.CLOUD
    assert decision.constraint_binding is False


def test_low_confidence_public_stays_local(cloud_enabled):
    decision = privacy_router.route(
        "Write a blog post.",
        classification=_classification(SensitivityLabel.PUBLIC, 0.20),
    )
    assert decision.placement is Placement.LOCAL
    assert any(r["reason"] == "privacy_constraint" for r in decision.rejected)


def test_abstention_stays_local_even_when_label_is_public():
    decision = privacy_router.route(
        "ambiguous",
        classification=_classification(SensitivityLabel.PUBLIC, 0.99, abstained=True),
    )
    assert decision.placement is Placement.LOCAL


def test_cost_advantage_cannot_override_the_constraint():
    """
    The point of expressing privacy as a feasible-set filter rather than a
    score term: there is no cost saving large enough to buy a cloud placement
    for sensitive content.
    """
    decision = privacy_router.route(
        "payroll data",
        classification=_classification(SensitivityLabel.CONFIDENTIAL, 1.0),
        est_input_tokens=10_000_000,
        est_output_tokens=10_000_000,
    )
    assert decision.placement is Placement.LOCAL


def test_router_picks_cheapest_among_feasible_candidates(cloud_enabled):
    decision = privacy_router.route(
        "Write a blog post.",
        classification=_classification(SensitivityLabel.PUBLIC, 0.95),
    )
    cloud_costs = [
        c.estimated_cost(100, 100)
        for c in privacy_router.candidates()
        if c.placement is Placement.CLOUD
    ]
    chosen = next(
        c for c in privacy_router.candidates() if c.model == decision.model
    ).estimated_cost(100, 100)
    assert chosen == min(cloud_costs)


def test_eval_override_opens_cloud_for_the_unconstrained_baseline():
    decision = privacy_router.route(
        "payroll",
        classification=_classification(SensitivityLabel.CONFIDENTIAL, 1.0),
        max_cloud_label="confidential",
    )
    assert Placement.CLOUD in decision.allowed_placements


def test_decision_audit_records_why_cloud_was_refused(cloud_enabled):
    decision = privacy_router.route("Charge card 4111 1111 1111 1111.")
    audit = decision.to_audit_dict()
    assert audit["placement"] == "local"
    assert audit["constraint_binding"] is True
    assert any(r["reason"] == "privacy_constraint" for r in audit["rejected"])
    # The audit trail must identify the detector without reproducing the match.
    assert "4111" not in str(audit)


# --- Explicit-mode enforcement ----------------------------------------------


def test_explicitly_requested_cloud_is_refused_for_sensitive_content(cloud_enabled):
    from app.runtime.exceptions import RuntimePolicyError
    from app.runtime.policy import runtime_policy
    from app.schemas.runtime import RuntimeGenerateRequest, RuntimeMode

    request = RuntimeGenerateRequest(
        prompt="Summarize the Q3 payroll and bonus allocation.",
        execution_mode=RuntimeMode.CLOUD,
    )
    with pytest.raises(RuntimePolicyError, match="Cloud execution refused"):
        runtime_policy.validate_request(request)


# --- Verifier ---------------------------------------------------------------


def test_verifier_rejects_degenerate_answers():
    report = response_verifier.verify("I don't know", {}, [])
    assert report.status == "FAILED"
    assert report.passed is False


def test_verifier_flags_ungrounded_rag_answer():
    aggregated = {"step_1": {"capability": "rag_answer", "output": {}}}
    sources = [{"content": "quarterly revenue grew across the retail division"}]
    report = response_verifier.verify(
        "Photosynthesis converts sunlight into chemical energy in plants.",
        aggregated,
        sources,
    )
    assert report.status == "FAILED"
    assert any("retrieved passages" in f for f in report.failures)


def test_verifier_passes_grounded_answer():
    aggregated = {"step_1": {"capability": "rag_answer", "output": {}}}
    sources = [
        {
            "content": "The deployment runbook requires a security signoff "
            "before phase three."
        }
    ]
    report = response_verifier.verify(
        "The deployment runbook requires a security signoff before phase three.",
        aggregated,
        sources,
    )
    assert report.status == "PASSED"
    assert report.confidence > 0.0


def test_verifier_catches_count_contradiction():
    aggregated = {
        "step_1": {
            "capability": "database_query",
            "output": {"rows": [], "row_count": 0},
        }
    }
    report = response_verifier.verify("I found 12 rows matching.", aggregated, [])
    assert report.checks["row_count_consistent"] is False
    assert report.status == "FAILED"


def test_verifier_skips_grounding_for_free_generation():
    aggregated = {"step_1": {"capability": "text_generation", "output": {}}}
    report = response_verifier.verify("Any invented prose at all.", aggregated, [])
    assert report.checks["grounding_applicable"] is False
    assert report.status == "PASSED"


# --- Quality judge ----------------------------------------------------------


def test_quality_judge_empty_answer_scores_zero_not_unmeasured():
    from app.evaluation.quality_judge import quality_judge

    judgment = quality_judge.judge(question="What is X?", answer="")
    assert judgment.judged is True
    assert judgment.overall == 0.0


def test_quality_judge_disabled_returns_unmeasured_not_zero():
    """
    judged=False must mean "not measured" -- an unreachable judge must never
    be scored as a bad answer. Disabling the judge is the cheapest way to
    exercise that branch deterministically, without depending on whether
    Ollama happens to be reachable in this environment.
    """
    from app.core.config import settings
    from app.evaluation.quality_judge import quality_judge

    original = settings.QUALITY_JUDGE_ENABLED
    settings.QUALITY_JUDGE_ENABLED = False
    try:
        judgment = quality_judge.judge(question="What is X?", answer="X is Y.")
    finally:
        settings.QUALITY_JUDGE_ENABLED = original

    assert judgment.judged is False
    assert judgment.overall is None


def test_quality_judgment_overall_averages_only_available_scores():
    from app.evaluation.quality_judge import QualityJudgment

    partial = QualityJudgment(faithfulness=1.0, relevance=None, completeness=0.5, judged=True)
    assert partial.overall == 0.75

    none_available = QualityJudgment(judged=False)
    assert none_available.overall is None


def test_quality_judge_prompt_template_does_not_crash_on_format():
    """
    Regression test for a real bug: the judge prompt embeds a literal JSON
    example ({"faithfulness": ...}) and is built with str.format(). Unescaped
    braces in that example make format() raise KeyError before the runtime is
    ever called -- unconditionally, network or no network. This must reach
    the (network-dependent, gracefully-handled) generate() call rather than
    crash inside prompt construction.
    """
    from app.evaluation.quality_judge import quality_judge

    judgment = quality_judge.judge(
        question="What is a load balancer?",
        answer="It distributes requests across servers.",
        context_snippets=["A load balancer spreads traffic across a server fleet."],
    )
    assert judgment.judged in (True, False)
    assert "KeyError" not in judgment.rationale


def test_second_rater_prompt_template_does_not_crash_on_format():
    """Same bug class, same fix, in the independent second-rater's prompt."""
    from app.evaluation.second_rater import rate_one

    label, reason = rate_one("Explain how TLS certificate validation works.")
    assert label is None or label in ("public", "internal", "confidential")
    assert "KeyError" not in reason


# --- Cohen's kappa (second_rater.py) ----------------------------------------


def test_cohens_kappa_perfect_agreement():
    from app.evaluation.second_rater import cohens_kappa

    pairs = [("public", "public"), ("internal", "internal"), ("confidential", "confidential")]
    assert cohens_kappa(pairs) == 1.0


def test_cohens_kappa_chance_level_agreement_is_near_zero():
    from app.evaluation.second_rater import cohens_kappa

    # Every label appears equally on both sides but paired so agreement is
    # exactly what chance alone would produce.
    pairs = [
        ("public", "internal"), ("public", "confidential"), ("public", "public"),
        ("internal", "public"), ("internal", "confidential"), ("internal", "internal"),
        ("confidential", "public"), ("confidential", "internal"), ("confidential", "confidential"),
    ]
    assert abs(cohens_kappa(pairs)) < 0.05


def test_cohens_kappa_empty_input():
    from app.evaluation.second_rater import cohens_kappa

    assert cohens_kappa([]) == 0.0


# --- Harness v2: stratified sampling and the anti-fixture guard ------------


def test_stratified_sample_is_balanced_across_labels():
    from app.evaluation.harness_v2 import stratified_sample

    rows = (
        [{"item_id": f"pub_{i}", "label": "public"} for i in range(20)]
        + [{"item_id": f"int_{i}", "label": "internal"} for i in range(20)]
        + [{"item_id": f"con_{i}", "label": "confidential"} for i in range(20)]
    )
    sample = stratified_sample(rows, n=9, seed=1)
    from collections import Counter

    counts = Counter(r["label"] for r in sample)
    assert len(sample) == 9
    assert counts == {"public": 3, "internal": 3, "confidential": 3}


def test_stratified_sample_is_deterministic_per_seed():
    from app.evaluation.harness_v2 import stratified_sample

    rows = [{"item_id": f"i_{i}", "label": "public"} for i in range(50)]
    a = stratified_sample(rows, n=10, seed=7)
    b = stratified_sample(rows, n=10, seed=7)
    c = stratified_sample(rows, n=10, seed=8)
    assert [r["item_id"] for r in a] == [r["item_id"] for r in b]
    assert a != c or [r["item_id"] for r in a] != [r["item_id"] for r in c]


def test_adapt_to_dataset_item_derives_expected_mode_from_rubric_label():
    from app.evaluation.harness_v2 import _adapt_to_dataset_item

    public_row = {"item_id": "p1", "text": "hello", "label": "public", "signal_type": "contextual"}
    confidential_row = {"item_id": "c1", "text": "hello", "label": "confidential", "signal_type": "explicit_identifier"}

    assert _adapt_to_dataset_item(public_row).expected_execution_mode == "cloud"
    assert _adapt_to_dataset_item(confidential_row).expected_execution_mode == "local"


def test_fixture_duplication_guard_catches_identical_latencies():
    """
    This is a regression guard for the exact corruption found in 44/46 of
    Week 1's historical evaluation artifacts: every row in a run reporting
    the same task, the same latency. The harness must refuse to treat that
    shape as a real result rather than silently report it.
    """
    from dataclasses import dataclass

    from app.evaluation.harness_v2 import assert_no_fixture_duplication

    @dataclass
    class FakeResult:
        task_id: str
        latency_ms: float

    suspicious = [FakeResult(f"t{i}", 120.0) for i in range(10)]
    try:
        assert_no_fixture_duplication(suspicious, context="test")
        raised = False
    except AssertionError:
        raised = True
    assert raised

    genuine = [FakeResult(f"t{i}", 100.0 + i * 7.3) for i in range(10)]
    assert_no_fixture_duplication(genuine, context="test")  # must not raise


def test_run_classifier_eval_end_to_end(tmp_path):
    """
    Regression test for a real bug: run_classifier_eval() called score() with a
    keyword argument (cloud_confidence=) that score()'s actual signature
    (rows, threshold) doesn't accept, so every harness run crashed with
    TypeError before producing a single number. Exercises the real call path
    rather than mocking score(), which is exactly what let the mismatch through
    the first time.
    """
    from app.evaluation.harness_v2 import run_classifier_eval

    exemplars_path = tmp_path / "exemplars.jsonl"
    eval_path = tmp_path / "eval.jsonl"
    exemplars_path.write_text(
        '{"text": "Explain how a load balancer works.", "label": "public"}\n'
        '{"text": "Summarize the internal roadmap sync notes.", "label": "internal"}\n',
        encoding="utf-8",
    )
    eval_path.write_text(
        '{"item_id": "t1", "text": "Refund the card 4111 1111 1111 1111.", "label": "confidential"}\n',
        encoding="utf-8",
    )

    result = run_classifier_eval(eval_path, exemplars_path)
    assert result["n"] == 1
    assert "safety" in result and "leak_rate" in result["safety"]


def test_baselines_survive_an_all_unmeasured_metric(monkeypatch):
    """
    Regression test for a real bug found by actually running the baseline
    sweep end-to-end for the first time: m_map.get(key, default) only falls
    back when the key is ABSENT. Since Week 1 made unmeasurable metrics
    report an honest None instead of a fabricated number, the key is present
    with value None whenever every task in a baseline run fails before
    reporting real tokens (e.g. every ALWAYS_LOCAL task, with Ollama down) --
    and int(None) used to crash before this file's fix.
    """
    import app.evaluation.baselines as baselines_mod
    from app.evaluation.baselines import BaselineRunner
    from app.evaluation.schemas import EvaluationConfigSchema, EvaluationResultItemSchema
    from app.evaluation.metrics import MetricsEngine

    # A single failed task produces exactly this shape: routing_accuracy and
    # completion_rate are real 0.0 (a task DID fail), but latency/tokens/cost
    # are None because nothing ever executed to measure them.
    failed_result = EvaluationResultItemSchema(
        task_id="t1", task_text="x", category="c", complexity="medium",
        privacy_level="public", expected_capability="text_generation",
        expected_execution_mode="local", routing_correct=False,
        completion_success=False, latency_ms=None, total_tokens=None,
        estimated_cost=None,
    )
    monkeypatch.setattr(
        baselines_mod.TaskExecutor, "execute_task",
        staticmethod(lambda **kwargs: failed_result),
    )

    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        results = BaselineRunner.run_baselines(
            db=db, tasks=[object()], config=EvaluationConfigSchema()
        )
    finally:
        db.close()

    assert len(results) == 4  # one per baseline name, none crashed
    for r in results:
        assert r.total_tokens == 0
        assert r.avg_latency_ms == 0.0


def test_always_local_override_maps_to_a_valid_execution_mode():
    """
    Regression test: override_mode="always_local" (what BaselineRunner passes
    for the ALWAYS_LOCAL baseline) must resolve to the literal string "local"
    before reaching SupervisorContext. It previously passed through
    unmapped and RuntimePolicy rejected every single task with
    "Invalid execution_mode 'always_local'" -- the ALWAYS_LOCAL baseline
    could never have completed a single task since it was introduced.
    """
    from app.evaluation.executor import TaskExecutor
    from app.evaluation.schemas import DatasetItemSchema, EvaluationConfigSchema

    task = DatasetItemSchema(
        task_id="t1", task="hello", category="c", complexity="medium",
        privacy_level="public", expected_capability="text_generation",
        expected_execution_mode="local",
    )
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        result = TaskExecutor.execute_task(
            db=db, task=task, config=EvaluationConfigSchema(), override_mode="always_local"
        )
    finally:
        db.close()

    assert result.error_type != "RuntimePolicyError"
    assert "Invalid execution_mode" not in (result.error_message or "")


def test_fixture_duplication_guard_catches_duplicate_task_ids():
    from dataclasses import dataclass

    from app.evaluation.harness_v2 import assert_no_fixture_duplication

    @dataclass
    class FakeResult:
        task_id: str
        latency_ms: float

    dup = [FakeResult("same_id", 100.0 + i) for i in range(5)]
    try:
        assert_no_fixture_duplication(dup, context="test")
        raised = False
    except AssertionError:
        raised = True
    assert raised


def test_preflight_reports_hardware_headroom():
    """
    A concurrent-load test found sweep latency variance correlates with RAM
    headroom, not just Ollama availability. preflight() must report actual
    RAM/CPU numbers on every run so that finding is attributable per-run
    rather than a one-off note in a doc, and must degrade to a reported
    error rather than crashing the whole preflight if psutil is unavailable.
    """
    from app.evaluation.harness_v2 import preflight

    status = preflight()
    assert "hardware" in status
    hw = status["hardware"]
    assert hw is not None, status.get("hardware_error")
    assert hw["ram_total_gb"] > 0
    assert 0 <= hw["ram_used_pct"] <= 100
    assert hw["cpu_logical_cores"] >= 1


def test_render_template_leaves_no_unsubstituted_placeholders():
    """
    Regression test for a real bug: GREETINGS/SIGNOFFS pool entries carry
    their own {name}/{sender} syntax (e.g. "Hi {name},"), and
    template.text.format(**entities) only runs once, so any template using
    {greeting}/{signoff} rendered literal "{name}"/"{sender}" text into 70 of
    419 corpus items across 9 templates. Exercises the real render path
    (not a mock) on every template that uses {greeting} or {signoff}.
    """
    import random

    from faker import Faker

    from app.evaluation.generate_privacy_corpus import TEMPLATES, render_template

    fake = Faker()
    Faker.seed(1)
    rng = random.Random(1)

    affected = [t for t in TEMPLATES if "{greeting}" in t.text or "{signoff}" in t.text]
    assert len(affected) == 9  # the exact count the bug report found

    for template in affected:
        row = render_template(template, fake, rng)
        assert "{name}" not in row["text"], f"{template.template_id}: unsubstituted {{name}}"
        assert "{sender}" not in row["text"], f"{template.template_id}: unsubstituted {{sender}}"


def test_run_baseline_seed_forces_cache_off(monkeypatch):
    """
    EvaluationConfigSchema.cache_enabled defaults True. Left on, the 4
    baselines in a seed run sequentially against the same items, and the
    same DB/cache persists across seeds -- AMOF would get free cache hits
    off an identical-text call an earlier baseline just made, biasing
    exactly the latency/cost numbers the sweep exists to compare fairly.
    run_baseline_seed() must override cache_enabled=False regardless of the
    schema default.
    """
    import app.evaluation.harness_v2 as harness_mod
    from app.evaluation.baselines import BaselineRunner

    captured_configs = []

    def fake_run_baselines(db, tasks, config):
        captured_configs.append(config)
        return []

    monkeypatch.setattr(BaselineRunner, "run_baselines", staticmethod(fake_run_baselines))

    eval_rows = [
        {"item_id": "e1", "text": "public text", "label": "public", "signal_type": "contextual"},
        {"item_id": "e2", "text": "internal text", "label": "internal", "signal_type": "contextual"},
        {"item_id": "e3", "text": "confidential text", "label": "confidential", "signal_type": "contextual"},
    ]
    harness_mod.run_baseline_seed(seed=0, sample_size=3, eval_rows=eval_rows)

    assert len(captured_configs) == 1
    assert captured_configs[0].cache_enabled is False


def test_sweep_checkpoints_per_seed_and_resume_skips_completed_seeds(tmp_path, monkeypatch):
    """
    Regression test for a real gap: main() previously wrote its output only
    once, after the ENTIRE seed loop finished -- a killed process (laptop
    closed, session interrupted) lost every already-completed seed, and
    "resume" meant rerunning from item 1 of seed 0. Each seed's result must
    now be written to disk the moment that seed finishes, and --resume must
    skip seeds whose checkpoint file already exists rather than recomputing
    them.
    """
    import app.evaluation.harness_v2 as harness_mod

    monkeypatch.setattr(harness_mod, "ARTIFACTS_DIR", tmp_path)
    monkeypatch.setattr(
        harness_mod, "preflight",
        lambda: {"database": True, "embeddings": False, "ollama_local": True, "cloud_litellm": False},
    )

    call_count = {"n": 0}

    def fake_run_baseline_seed(seed, sample_size, eval_rows):
        call_count["n"] += 1
        return {
            "seed": seed, "sample_size": sample_size, "elapsed_s": 1.0,
            "hardware_before": {}, "hardware_after": {},
            "baselines": [{"baseline_name": "AMOF", "completion_rate": 1.0,
                            "routing_accuracy": 1.0, "privacy_leak_rate": 0.0,
                            "p95_latency_ms": 100.0}],
        }

    monkeypatch.setattr(harness_mod, "run_baseline_seed", fake_run_baseline_seed)

    # main() reads args.eval as newline-delimited JSON and wraps it in
    # "[...]" -- an empty file is enough since fake_run_baseline_seed above
    # never actually looks at eval_rows.
    (tmp_path / "fake.jsonl").write_text("", encoding="utf-8")
    argv = ["--seeds", "2", "--sample-size", "3", "--force", "--run-tag", "resumetest",
            "--eval", str(tmp_path / "fake.jsonl")]

    harness_mod.main(argv)
    assert call_count["n"] == 2  # both seeds actually ran, first time through
    assert (tmp_path / "checkpoint_resumetest_seed0.json").exists()
    assert (tmp_path / "checkpoint_resumetest_seed1.json").exists()

    # Second invocation, --resume: neither seed should be recomputed.
    harness_mod.main(argv + ["--resume"])
    assert call_count["n"] == 2  # unchanged -- both seeds skipped, loaded from disk
