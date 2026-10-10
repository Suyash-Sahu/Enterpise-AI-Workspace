"""
Phase 30: Attribution regression tests.

Proves that on single-step plans, FailureAttributor agrees with the old
steps[-1] behavior, so the change is backward-safe for the existing case.
"""
import json
import pytest
from app.supervisor.attribution import FailureAttributor, FAILURE_CATEGORIES
from app.schemas.supervisor import PlanStep, SupervisorPlan


CAPABILITIES = [
    "rag_search",
    "rag_answer",
    "database_query",
    "text_generation",
    "document_summary",
]


def _plan_one(cap, status="FAILED"):
    step = PlanStep(
        step_id="step_1", capability=cap, status=status,
        depends_on=[], input_template={},
    )
    return SupervisorPlan(
        plan_id="reg_plan", request_id="reg_req",
        steps=[step], max_steps=5,
    )


def _ver_failed():
    return json.dumps({"status": "FAILED", "confidence": 0.1, "failures": ["generic failure"], "checks": {}})


class TestAttributionRegression:
    """Single-step regression: attributor must agree with steps[-1] for all capabilities."""

    @pytest.mark.parametrize("cap", CAPABILITIES)
    def test_single_step_matches_last_step_proxy(self, cap):
        """Attributor on a one-step FAILED plan must blame that exact step."""
        plan = _plan_one(cap)
        attr = FailureAttributor().attribute(plan, {"step_1": _ver_failed()})
        # Old proxy: blamed plan.steps[-1] (which is step_1 for a 1-step plan)
        assert attr.suspect_step_id == "step_1", (
            f"Regression: single-step plan with cap={cap} should blame step_1 (old proxy behavior)"
        )

    @pytest.mark.parametrize("cap", CAPABILITIES)
    def test_single_step_category_is_taxonomy_member(self, cap):
        """Category is always from the closed set regardless of capability."""
        plan = _plan_one(cap)
        attr = FailureAttributor().attribute(plan, {"step_1": _ver_failed()})
        assert attr.failure_category in FAILURE_CATEGORIES

    def test_attribution_to_dict_serializable(self):
        """Attribution.to_dict() must be JSON-serializable for SupervisorResponse."""
        plan = _plan_one("rag_search")
        attr = FailureAttributor().attribute(plan, {"step_1": _ver_failed()})
        d = attr.to_dict()
        import json
        serialized = json.dumps(d)
        assert "suspect_step_id" in serialized
        assert "failure_category" in serialized

    def test_empty_plan_does_not_raise(self):
        """An empty-step plan must return a fallback attribution, not raise."""
        plan = SupervisorPlan(
            plan_id="empty", request_id="empty",
            steps=[], max_steps=5,
        )
        attr = FailureAttributor().attribute(plan, {})
        assert attr.suspect_step_id == "unknown"
        assert attr.confidence == 0.0
