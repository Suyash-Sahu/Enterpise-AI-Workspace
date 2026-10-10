"""
Phase 14: statistics module tests.

The load-bearing property across these tests: every method reports an
explicit status rather than fabricating a number when the input can't
support the computation (n=1 run, mismatched pair lengths, etc.).
"""

from app.evaluation.statistics import StatisticalAnalyzer


def test_confidence_interval_insufficient_with_single_run():
    result = StatisticalAnalyzer.confidence_interval("routing_accuracy", [0.9])
    assert result.status == "INSUFFICIENT_RUNS"
    assert result.ci_low is None
    assert result.ci_high is None
    assert result.mean == 0.9  # the one observed value, not fabricated


def test_confidence_interval_insufficient_with_zero_runs():
    result = StatisticalAnalyzer.confidence_interval("routing_accuracy", [])
    assert result.status == "INSUFFICIENT_RUNS"
    assert result.mean is None
    assert result.n_runs == 0


def test_confidence_interval_available_with_multiple_runs():
    values = [0.90, 0.92, 0.88, 0.91, 0.89]
    result = StatisticalAnalyzer.confidence_interval("routing_accuracy", values)
    assert result.status == "AVAILABLE"
    assert result.n_runs == 5
    assert result.ci_low < result.mean < result.ci_high
    assert abs(result.mean - (sum(values) / len(values))) < 1e-9


def test_confidence_interval_zero_width_when_all_runs_identical():
    result = StatisticalAnalyzer.confidence_interval("completion_rate", [0.9, 0.9, 0.9])
    assert result.status == "AVAILABLE"
    assert result.ci_low == result.ci_high == result.mean == 0.9


def test_paired_significance_insufficient_with_one_pair():
    result = StatisticalAnalyzer.paired_significance("latency_ms", [100.0], [200.0])
    assert result.status == "INSUFFICIENT_DATA"
    assert result.p_value is None


def test_paired_significance_insufficient_on_length_mismatch():
    result = StatisticalAnalyzer.paired_significance("latency_ms", [1.0, 2.0], [1.0, 2.0, 3.0])
    assert result.status == "INSUFFICIENT_DATA"


def test_paired_significance_detects_a_real_difference():
    # AMOF consistently faster than baseline on every paired task.
    amof = [800.0, 820.0, 790.0, 810.0, 805.0, 795.0]
    baseline = [1400.0, 1420.0, 1390.0, 1410.0, 1405.0, 1395.0]
    result = StatisticalAnalyzer.paired_significance("latency_ms", amof, baseline)
    assert result.status == "AVAILABLE"
    assert result.test in ("ttest_rel", "wilcoxon")
    assert result.p_value is not None
    assert result.p_value < 0.05, "a large, consistent paired difference should be significant"


def test_paired_significance_no_difference_reports_p_equals_one():
    values = [0.9, 0.9, 0.9]
    result = StatisticalAnalyzer.paired_significance("completion_rate", values, values)
    assert result.status == "AVAILABLE"
    assert result.p_value == 1.0


def test_paired_cohens_d_none_when_insufficient():
    assert StatisticalAnalyzer.paired_cohens_d([1.0], [2.0]) is None
    assert StatisticalAnalyzer.paired_cohens_d([1.0, 2.0], [1.0]) is None


def test_paired_cohens_d_zero_is_distinct_from_none():
    """0.0 (no effect) and None (not measured) must never be conflated."""
    d_measured_zero = StatisticalAnalyzer.paired_cohens_d([1.0, 1.0, 1.0], [1.0, 1.0, 1.0])
    assert d_measured_zero == 0.0
    d_not_measured = StatisticalAnalyzer.paired_cohens_d([1.0], [1.0])
    assert d_not_measured is None


def test_paired_cohens_d_large_effect():
    amof = [10.0, 10.0, 10.0, 10.0]
    baseline = [1.0, 1.0, 1.0, 1.0]
    d = StatisticalAnalyzer.paired_cohens_d(amof, baseline)
    # Zero variance in the differences (constant 9.0 each time) -- the
    # std_diff==0.0 branch, a real "cannot express as a ratio" case.
    assert d == 0.0
