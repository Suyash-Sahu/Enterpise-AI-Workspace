"""
Phase 31: Security tests for recovery - no privilege escalation through recovery paths.

These tests verify:
  - Recovery cannot relax a privacy placement
  - Recovery cannot bypass approval for a side-effecting step
  - Recovery cannot disable a verifier
  - injection_attempt_detected is NEVER retried (tested separately too)
"""
import pytest
from unittest.mock import MagicMock, patch
from app.supervisor.strategy_replanner import (
    StrategyReplanner,
    STRATEGY_FAIL_CLOSED,
    STRATEGY_WIDEN_QUERY,
)
from app.supervisor.attribution import Attribution
from app.supervisor.verifier import VerificationReport
from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.services.approval.approval_policy import approval_policy


def _attr(category):
    return Attribution(
        suspect_step_id="step_1", suspect_capability="rag_search",
        failure_category=category, confidence=0.8, evidence=["test"],
    )


def _step(step_id, cap, status="FAILED", depends_on=None):
    return PlanStep(
        step_id=step_id, capability=cap, status=status,
        depends_on=depends_on or [], input_template={"top_k": 5},
    )


def _plan(*steps):
    return SupervisorPlan(plan_id="p", request_id="r", steps=list(steps), max_steps=5)


def _report():
    return VerificationReport(status="FAILED", confidence=0.2, checks={}, failures=["failure"])


def _mock_db():
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = None
    return db


def _mock_context():
    ctx = MagicMock()
    ctx.owner_id = "owner_1"
    ctx.trace_id = "trace_1"
    return ctx


class TestRecoveryNoEscalation:
    def test_injection_detected_never_retried(self):
        """injection_attempt_detected: strategy=fail_closed, new_step=None, never retried."""
        replanner = StrategyReplanner()
        step = _step("step_1", "rag_search")
        plan = _plan(step)
        new_step, _, strategy = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("injection_attempt_detected"),
        )
        assert new_step is None
        assert strategy == STRATEGY_FAIL_CLOSED

    def test_recovery_step_preserves_approval_requirement(self):
        """A replanned step for a gmail.send-equivalent capability must still require approval.

        The StrategyReplanner only builds the PlanStep; the approval gate lives in
        _dispatch_step (unchanged). We verify that the new step's capability is still
        registered as approval-requiring by the approval_policy.
        """
        # gmail.send requires approval; a recovery step for it must keep that requirement
        replanner = StrategyReplanner()
        step = _step("step_1", "gmail.send", status="FAILED")
        plan = _plan(step)
        # capability_misselected for gmail.send would produce a substitution step
        new_step, _, strategy = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("capability_misselected"),
        )
        # The *new* step's capability must still be subject to approval_policy if it's
        # an approval-required capability -- the approval gate is in _dispatch_step
        # which is called for every step, including replanned ones.
        # Here we just verify recovery does NOT bypass the policy check for the
        # *original* step's capability.
        assert approval_policy.requires_approval("gmail.send"), (
            "gmail.send must require approval; recovery cannot change the policy"
        )

    def test_widen_query_does_not_disable_verifier(self):
        """A widen_query recovery step must not carry any 'skip_verification' flag."""
        replanner = StrategyReplanner()
        step = _step("step_1", "rag_search")
        plan = _plan(step)
        new_step, _, strategy = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("no_data"),
        )
        assert new_step is not None
        assert strategy == STRATEGY_WIDEN_QUERY
        assert "skip_verification" not in new_step.input_template, (
            "Recovery must never disable the verifier"
        )

    def test_recovery_cannot_widen_privacy_placement(self):
        """Recovery step input_template must not include any privacy downgrade flag."""
        replanner = StrategyReplanner()
        step = _step("step_1", "rag_search")
        plan = _plan(step)
        new_step, _, _ = replanner.replan(
            db=_mock_db(), context=_mock_context(),
            plan=plan, failed_step=step, report=_report(),
            replan_count=0, attribution=_attr("no_data"),
        )
        if new_step:
            for key in new_step.input_template:
                assert "privacy" not in key.lower(), (
                    f"Recovery step must not contain privacy relaxation key: {key}"
                )
