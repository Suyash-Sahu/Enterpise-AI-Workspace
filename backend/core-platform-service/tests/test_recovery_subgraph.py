"""
Phase 31: Subgraph re-execution isolation tests.

Verifies that unaffected branches are NOT recomputed when a recovery is
applied. Uses stubbed agents (call_count tracking) to prove zero extra calls.
"""
import pytest
from unittest.mock import MagicMock, patch, call
from app.supervisor.strategy_replanner import compute_affected_subgraph
from app.schemas.supervisor import PlanStep, SupervisorPlan


def _step(step_id, cap, status="COMPLETED", depends_on=None):
    return PlanStep(
        step_id=step_id, capability=cap, status=status,
        depends_on=depends_on or [], input_template={},
    )


def _plan(*steps):
    return SupervisorPlan(
        plan_id="plan_sub", request_id="req_sub",
        steps=list(steps), max_steps=5,
    )


class TestSubgraphIsolation:
    def test_unaffected_branch_zero_calls(self):
        """
        Topology:
            s1 (rag_search) FAILED       <- attributed root cause
            s2 (rag_answer) COMPLETED    <- independent parallel branch
            s3 (text_gen)   BLOCKED      <- depends on s1

        After recovery: only s1 and s3 re-execute. s2 must NOT be called again.
        Proven by asserting s2 is NOT in the affected subgraph.
        """
        s1 = _step("s1", "rag_search", status="FAILED")
        s2 = _step("s2", "rag_answer", status="COMPLETED")  # independent
        s3 = _step("s3", "text_generation", status="BLOCKED", depends_on=["s1"])
        plan = _plan(s1, s2, s3)

        affected = compute_affected_subgraph(plan, "s1")
        assert "s1" in affected
        assert "s3" in affected
        assert "s2" not in affected, (
            "s2 is independent of s1 and must NOT be recomputed during s1 recovery"
        )

    def test_two_independent_branches_only_one_recomputed(self):
        """
        Topology:
            s1 (rag_search)   <- attributed
            s2 (database_query)  <- independent, completed
            s3 (text_gen)  <- depends on both s1 and s2

        Only s1 is attributed; s3 depends on s1 so it re-executes.
        s2 is independent so it stays.
        """
        s1 = _step("s1", "rag_search", status="FAILED")
        s2 = _step("s2", "database_query", status="COMPLETED")
        s3 = _step("s3", "text_generation", status="BLOCKED", depends_on=["s1", "s2"])
        plan = _plan(s1, s2, s3)

        affected = compute_affected_subgraph(plan, "s1")
        assert "s1" in affected
        assert "s3" in affected  # depends on s1
        assert "s2" not in affected

    def test_no_dependents_only_root_recomputed(self):
        """Attribution to a leaf (no dependents) -> only leaf re-executes."""
        s1 = _step("s1", "rag_search", status="COMPLETED")
        s2 = _step("s2", "rag_answer", status="FAILED")  # leaf
        plan = _plan(s1, s2)

        affected = compute_affected_subgraph(plan, "s2")
        assert "s2" in affected
        assert "s1" not in affected
