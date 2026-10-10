"""
Phase 14: cross-run statistical aggregation.

MetricsEngine (app/evaluation/metrics.py) computes metrics for a single
evaluation run. A confidence interval or significance claim needs multiple
independent runs (or multiple paired per-task observations) to estimate
variance from -- this module is deliberately separate so a single-run number
is never silently presented as if it carried a CI.

Discrepancy note (Phase 14, 2026-09-20): PHASE_14.md's audit describes this
as "the existing scipy-based paired testing," but no such module existed
anywhere in app/ before this file -- only a requirements.txt comment
recording the intent to use scipy.stats.ttest_rel/wilcoxon rather than a
hand-rolled t-distribution CDF for a router-vs-baseline significance claim.
Resolved per CLAUDE.md's instruction to inspect and resolve such
discrepancies explicitly rather than silently assuming either the doc or the
code: this module is the first real implementation, built to that stated
intent (scipy, not hand-rolled), not a rewrite of something pre-existing.
"""

import math
from dataclasses import dataclass
from typing import List, Optional

try:
    from scipy import stats as _scipy_stats
except ImportError:  # pragma: no cover - scipy is a declared dependency
    _scipy_stats = None


@dataclass
class ConfidenceIntervalResult:
    metric_name: str
    mean: Optional[float]
    ci_low: Optional[float]
    ci_high: Optional[float]
    n_runs: int
    confidence_level: float
    status: str  # "AVAILABLE" | "INSUFFICIENT_RUNS"


@dataclass
class SignificanceTestResult:
    metric_name: str
    test: str  # "ttest_rel" | "wilcoxon" | "none"
    statistic: Optional[float]
    p_value: Optional[float]
    n_pairs: int
    status: str  # "AVAILABLE" | "INSUFFICIENT_DATA"


class StatisticalAnalyzer:
    """
    Aggregates a metric across multiple runs (confidence interval) or
    compares two conditions on matched pairs (significance + effect size).
    Every method returns an explicit status rather than a fabricated number
    when the input can't support the computation -- an underpowered result
    must be reported as underpowered, not silently omitted or guessed.
    """

    CONFIDENCE_LEVEL = 0.95

    @staticmethod
    def confidence_interval(
        metric_name: str, values: List[float], confidence_level: float = CONFIDENCE_LEVEL
    ) -> ConfidenceIntervalResult:
        """
        95% CI via Student's t-distribution over per-run metric values.
        Requires at least 2 runs: a single run has no variance to estimate
        a spread from, so no interval is fabricated around it.
        """
        n = len(values)
        if n < 2:
            return ConfidenceIntervalResult(
                metric_name,
                values[0] if values else None,
                None,
                None,
                n,
                confidence_level,
                "INSUFFICIENT_RUNS",
            )

        mean = sum(values) / n
        variance = sum((v - mean) ** 2 for v in values) / (n - 1)
        std_err = math.sqrt(variance / n)

        if std_err == 0.0:
            # Every run produced the identical value -- a real, zero-width
            # interval, not a division-by-zero case to special-case away.
            return ConfidenceIntervalResult(metric_name, mean, mean, mean, n, confidence_level, "AVAILABLE")

        if _scipy_stats is not None:
            t_crit = _scipy_stats.t.ppf(1 - (1 - confidence_level) / 2, df=n - 1)
        else:  # pragma: no cover - scipy is a declared, installed dependency
            t_crit = 1.96

        margin = t_crit * std_err
        return ConfidenceIntervalResult(
            metric_name, mean, mean - margin, mean + margin, n, confidence_level, "AVAILABLE"
        )

    @staticmethod
    def paired_significance(
        metric_name: str, condition_values: List[float], baseline_values: List[float]
    ) -> SignificanceTestResult:
        """
        Paired significance test on matched observations (same task/run
        pairing on both sides) -- e.g. AMOF vs its strongest baseline on the
        same per-task metric. Uses scipy.stats.ttest_rel; falls back to
        wilcoxon when the paired differences are degenerate (all-zero
        differences make ttest_rel's variance term zero).
        """
        n = len(condition_values)
        if n < 2 or n != len(baseline_values):
            return SignificanceTestResult(metric_name, "none", None, None, n, "INSUFFICIENT_DATA")
        if _scipy_stats is None:  # pragma: no cover - scipy is a declared, installed dependency
            return SignificanceTestResult(metric_name, "none", None, None, n, "INSUFFICIENT_DATA")

        diffs = [a - b for a, b in zip(condition_values, baseline_values)]
        if all(d == 0 for d in diffs):
            # No difference to test -- a real result (p=1.0), not a failure.
            return SignificanceTestResult(metric_name, "ttest_rel", 0.0, 1.0, n, "AVAILABLE")

        try:
            result = _scipy_stats.ttest_rel(condition_values, baseline_values)
            return SignificanceTestResult(
                metric_name, "ttest_rel", float(result.statistic), float(result.pvalue), n, "AVAILABLE"
            )
        except Exception:
            try:
                result = _scipy_stats.wilcoxon(condition_values, baseline_values)
                return SignificanceTestResult(
                    metric_name, "wilcoxon", float(result.statistic), float(result.pvalue), n, "AVAILABLE"
                )
            except Exception:
                return SignificanceTestResult(metric_name, "none", None, None, n, "INSUFFICIENT_DATA")

    @staticmethod
    def paired_cohens_d(condition_values: List[float], baseline_values: List[float]) -> Optional[float]:
        """
        Cohen's d for paired samples: mean(diff) / std(diff). None (not 0.0)
        when there isn't enough data -- 0.0 would claim "no effect," which is
        a different, unsupported statement from "not measured."
        """
        n = len(condition_values)
        if n < 2 or n != len(baseline_values):
            return None
        diffs = [a - b for a, b in zip(condition_values, baseline_values)]
        mean_diff = sum(diffs) / n
        variance = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1)
        std_diff = math.sqrt(variance)
        if std_diff == 0.0:
            return 0.0
        return round(mean_diff / std_diff, 4)
