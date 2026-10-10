"""
Phase 30: Topological attribution ordering tests.

Dedicated file for the two-failed-step earliest-ancestor rule.
"""
import json
import pytest
from app.supervisor.attribution import FailureAttributor
from app.schemas.supervisor import PlanStep, SupervisorPlan


def _plan(*steps):
    return SupervisorPlan(
        plan_id="topo_plan", request_id="topo_req", steps=list(steps), max_steps=5
    )


def _step(step_id, cap, status="FAILED", depends_on=None):
    return PlanStep(
        step_id=step_id, capability=cap, status=status,
        depends_on=depends_on or [], input_template={},
    )


def _ver(failures):
    return json.dumps({"status": "FAILED", "confidence": 0.1, "failures": failures, "checks": {}})


class TestTopologicalPrecendenceRule:
    """The earliest failing ancestor in topological order is blamed, not the latest."""

    def test_three_step_chain_earliest_blamed(self):
        """Steps: s1 -> s2 -> s3. s1 and s2 both fail. s1 wins."""
        s1 = _step("s1", "rag_search", depends_on=[])
        s2 = _step("s2", "database_query", depends_on=["s1"])
        s3 = _step("s3", "text_generation", status="BLOCKED", depends_on=["s2"])
        plan = _plan(s1, s2, s3)
        attr = FailureAttributor().attribute(plan, {
            "s1": _ver(["no data"]),
            "s2": _ver(["contradiction"]),
            "s3": None,
        })
        assert attr.suspect_step_id == "s1", (
            "s1 is at topo position 0; it must be blamed, not s2"
        )

    def test_fan_out_branches_both_fail_first_wins(self):
        """s1 (source A) and s2 (source B) are independent parallel branches.
        Both fail. Plan order places s1 before s2, so s1 is blamed."""
        s1 = _step("s1", "rag_search", depends_on=[])
        s2 = _step("s2", "database_query", depends_on=[])
        s3 = _step("s3", "text_generation", status="BLOCKED", depends_on=["s1", "s2"])
        plan = _plan(s1, s2, s3)
        attr = FailureAttributor().attribute(plan, {
            "s1": _ver(["empty result"]),
            "s2": _ver(["tool error"]),
            "s3": None,
        })
        # s1 at index 0, s2 at index 1 -- s1 wins
        assert attr.suspect_step_id == "s1"

    def test_later_step_fails_blames_that_step(self):
        """Only the third step fails. It must be blamed, not s1 or s2."""
        s1 = _step("s1", "rag_search", status="COMPLETED")
        s2 = _step("s2", "database_query", status="COMPLETED", depends_on=["s1"])
        s3 = _step("s3", "text_generation", status="FAILED", depends_on=["s2"])
        plan = _plan(s1, s2, s3)
        attr = FailureAttributor().attribute(plan, {
            "s1": None, "s2": None,
            "s3": _ver(["unsupported claim"]),
        })
        assert attr.suspect_step_id == "s3"

    def test_confidence_higher_with_single_failure(self):
        """Confidence is higher when exactly one step fails (clearer diagnosis)."""
        s1 = _step("s1", "rag_search")
        plan_one = _plan(s1)
        attr_one = FailureAttributor().attribute(plan_one, {"s1": _ver(["no data"])})

        s2 = _step("s2", "database_query")
        plan_two = _plan(s1, s2)
        attr_two = FailureAttributor().attribute(plan_two, {
            "s1": _ver(["no data"]),
            "s2": _ver(["timeout"]),
        })
        assert attr_one.confidence >= attr_two.confidence, (
            "Attribution should be more confident when only one step failed"
        )
