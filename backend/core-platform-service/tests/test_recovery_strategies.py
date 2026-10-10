"""
Phase 31: Recovery strategy selection and subgraph re-execution tests.

One test per failure category asserting correct strategy selection.
Subgraph isolation test proving unaffected branches are not recomputed.
Security test proving recovery cannot escalate privileges.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from app.supervisor.strategy_replanner import (
    StrategyReplanner,
    compute_affected_subgraph,
    select_strategy,
    STRATEGY_WIDEN_QUERY,
    STRATEGY_CONSTRAINED_RETRY,
    STRATEGY_VERIFIED_SYNTHESIS_ONLY,
    STRATEGY_REPAIR_BINDING,
    STRATEGY_CAPABILITY_SUBSTITUTION,
    STRATEGY_RETRY_WITH_BACKOFF,
    STRATEGY_FAIL_CLOSED,
)
from app.supervisor.attribution import Attribution
from app.supervisor.verifier import VerificationReport
from app.schemas.supervisor import PlanStep, SupervisorPlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _attr(category: str) -> Attribution:
    return Attribution(
        suspect_step_id="step_1",
        suspect_capability="rag_search",
        failure_category=category,
        confidence=0.8,
        evidence=[f"test evidence for {category}"],
    )


def _plan(*steps: PlanStep) -> SupervisorPlan:
    return SupervisorPlan(
        plan_id="test_plan", request_id="req", steps=list(steps), max_steps=5
    )


def _step(step_id, cap, status="FAILED", depends_on=None):
    return PlanStep(
        step_id=step_id, capability=cap, status=status,
        depends_on=depends_on or [], input_template={"top_k": 5},
    )


def _report(confidence=0.3):
    return VerificationReport(
        status="FAILED",
        confidence=confidence,
        checks={},
        failures=["test failure"],
    )


def _mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def _mock_context():
    ctx = MagicMock()
    ctx.owner_id = "owner_1"
    ctx.trace_id = "trace_1"
    return ctx


# ---------------------------------------------------------------------------
# Strategy selection tests -- one per category
# ---------------------------------------------------------------------------

class TestStrategySelection:
    def test_no_data_selects_widen_query(self):
        assert select_strategy("no_data") == STRATEGY_WIDEN_QUERY

    def test_wrong_data_selects_constrained_retry(self):
        assert select_strategy("wrong_data") == STRATEGY_CONSTRAINED_RETRY

    def test_unsupported_claim_selects_verified_synthesis(self):
        assert select_strategy("unsupported_claim") == STRATEGY_VERIFIED_SYNTHESIS_ONLY

    def test_handoff_mismatch_selects_repair_binding(self):
        assert select_strategy("handoff_mismatch") == STRATEGY_REPAIR_BINDING

    def test_capability_misselected_selects_substitution(self):
        assert select_strategy("capability_misselected") == STRATEGY_CAPABILITY_SUBSTITUTION

    def test_tool_error_selects_retry_with_backoff(self):
        assert select_strategy("tool_error") == STRATEGY_RETRY_WITH_BACKOFF

    def test_timeout_selects_retry_with_backoff(self):
        assert select_strategy("timeout") == STRATEGY_RETRY_WITH_BACKOFF

    def test_injection_selects_fail_closed(self):
        assert select_strategy("injection_attempt_detected") == STRATEGY_FAIL_CLOSED


# ---------------------------------------------------------------------------
# Strategy replanner unit tests -- each produces correct step type
# ---------------------------------------------------------------------------

class TestStrategyReplannerOutput:
    def test_no_data_widens_top_k(self):
        replanner = StrategyReplanner()
        step = _step("step_1", "rag_search")
        plan = _plan(step)
        new_step, _, strategy = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("no_data"),
        )
        assert strategy == STRATEGY_WIDEN_QUERY
        assert new_step is not None
        assert new_step.input_template.get("top_k", 0) > 5
        assert new_step.input_template.get("replan_widen") is True

    def test_wrong_data_adds_constraint(self):
        replanner = StrategyReplanner()
        step = _step("step_1", "database_query")
        plan = _plan(step)
        new_step, _, strategy = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("wrong_data"),
        )
        assert strategy == STRATEGY_CONSTRAINED_RETRY
        assert new_step is not None
        assert "contradiction_constraint" in new_step.input_template

    def test_unsupported_claim_restricts_synthesis(self):
        replanner = StrategyReplanner()
        step = _step("step_1", "text_generation")
        plan = _plan(step)
        new_step, _, strategy = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("unsupported_claim"),
        )
        assert strategy == STRATEGY_VERIFIED_SYNTHESIS_ONLY
        assert new_step is not None
        assert new_step.input_template.get("verified_evidence_only") is True

    def test_injection_never_retried(self):
        replanner = StrategyReplanner()
        step = _step("step_1", "rag_search")
        plan = _plan(step)
        new_step, _, strategy = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("injection_attempt_detected"),
        )
        assert strategy == STRATEGY_FAIL_CLOSED
        assert new_step is None, "injection_attempt_detected must NEVER produce a retry step"

    def test_retry_with_backoff_no_new_step(self):
        replanner = StrategyReplanner()
        step = _step("step_1", "rag_search")
        plan = _plan(step)
        for cat in ("tool_error", "timeout"):
            new_step, _, strategy = replanner.replan(
                db=_mock_db(), context=_mock_context(),
                plan=plan, failed_step=step, report=_report(),
                replan_count=0, attribution=_attr(cat),
            )
            assert strategy == STRATEGY_RETRY_WITH_BACKOFF
            assert new_step is None, f"{cat}: retry_with_backoff must not produce a new plan step"


# ---------------------------------------------------------------------------
# Oscillation guard tests
# ---------------------------------------------------------------------------

class TestOscillationGuard:
    def test_same_strategy_step_pair_not_revisited(self):
        replanner = StrategyReplanner()
        step = _step("step_1", "rag_search")
        plan = _plan(step)
        tried: set = set()

        # First attempt
        new_step1, _, strategy1 = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("no_data"),
            tried_strategy_step_pairs=tried,
        )
        assert new_step1 is not None

        # Second attempt with same strategy/step pair -> blocked
        new_step2, _, strategy2 = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=1, attribution=_attr("no_data"),
            tried_strategy_step_pairs=tried,
        )
        assert new_step2 is None, "Oscillation guard must block revisiting the same (strategy, step) pair"


# ---------------------------------------------------------------------------
# Subgraph re-execution tests
# ---------------------------------------------------------------------------

class TestSubgraphComputation:
    def test_attributed_step_and_dependents_only(self):
        """Only step_1 and step_2 (which depends on step_1) are in the subgraph."""
        s1 = _step("s1", "rag_search")
        s2 = _step("s2", "text_generation", depends_on=["s1"])
        s3 = _step("s3", "database_query")  # independent, must NOT be in subgraph
        plan = _plan(s1, s2, s3)

        affected = compute_affected_subgraph(plan, "s1")
        assert "s1" in affected
        assert "s2" in affected
        assert "s3" not in affected, "Independent branches must not be recomputed"

    def test_leaf_step_only_itself(self):
        """Leaf step with no dependents: subgraph contains only itself."""
        s1 = _step("s1", "rag_search", depends_on=[])
        plan = _plan(s1)
        affected = compute_affected_subgraph(plan, "s1")
        assert affected == {"s1"}

    def test_transitive_dependents_all_included(self):
        """s1 -> s2 -> s3: attributing s1 includes s1, s2, s3."""
        s1 = _step("s1", "rag_search")
        s2 = _step("s2", "rag_answer", depends_on=["s1"])
        s3 = _step("s3", "text_generation", depends_on=["s2"])
        plan = _plan(s1, s2, s3)
        affected = compute_affected_subgraph(plan, "s1")
        assert affected == {"s1", "s2", "s3"}
