"""
Phase 27 tests: Parallel state write conflict detection and sequential ablation arm.
"""
import uuid
from unittest.mock import patch
import pytest

from app.runtime.exceptions import RuntimePolicyError
from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.schemas.execution import ExecutionResponse, ExecutionStatus
from app.supervisor.context import SupervisorContext
from app.supervisor.policies import supervisor_policy
from app.supervisor.supervisor import amof_supervisor
from app.db.database import Base, SessionLocal, engine


def test_independent_steps_writing_same_state_key_rejected_at_plan_validation():
    """
    inbox.classify (InboxAgent) writes ["inbox_findings"].
    inbox.draft_reply (InboxAgent) also writes ["inbox_findings"].
    If two independent steps specify these capabilities, validate_dag_plan
    must raise RuntimePolicyError.
    """
    step1 = PlanStep(step_id="step_1", capability="inbox.classify", depends_on=[])
    step2 = PlanStep(step_id="step_2", capability="inbox.draft_reply", depends_on=[])

    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1, step2])

    assert "mutually independent steps" in str(exc_info.value)
    assert "inbox_findings" in str(exc_info.value)


def test_dependent_steps_writing_same_state_key_are_allowed():
    """
    If step_2 depends on step_1 (step_2 -> step_1), they execute sequentially.
    Writing to the same state key sequentially is allowed.
    """
    step1 = PlanStep(step_id="step_1", capability="inbox.classify", depends_on=[])
    step2 = PlanStep(step_id="step_2", capability="inbox.draft_reply", depends_on=["step_1"])

    # Must not raise
    supervisor_policy.validate_dag_plan([step1, step2])


def test_sequential_ablation_arm_reproduces_phase_26_behavior():
    """
    With SUPERVISOR_PARALLEL_ENABLED=False, execution runs sequentially in the main thread.
    """
    Base.metadata.create_all(bind=engine)

    plan = SupervisorPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:8]}",
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        steps=[
            PlanStep(step_id="A", capability="text_generation", depends_on=[]),
            PlanStep(step_id="B", capability="text_generation", depends_on=[]),
        ],
    )

    executed = []

    def tracking_dispatch(db, context, capability, resolved_input, step_id):
        executed.append(step_id)
        return ExecutionResponse(
            execution_id=f"exec_{step_id}",
            status=ExecutionStatus.COMPLETED,
            task_type=capability,
            result={"result": {"generated_text": "ok"}},
            execution_time=0.01,
        )

    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id="1",
            question="ablation test",
            hitl_enabled=False,
            verification_enabled=False,
        )

        with patch("app.core.config.settings.SUPERVISOR_PARALLEL_ENABLED", False):
            with patch(
                "app.supervisor.supervisor.supervisor_execution_router.dispatch",
                side_effect=tracking_dispatch,
            ):
                res = amof_supervisor.run(db=db, context=context, preset_plan=plan)

        assert res.status == "COMPLETED"
        assert executed == ["A", "B"]
    finally:
        db.close()
