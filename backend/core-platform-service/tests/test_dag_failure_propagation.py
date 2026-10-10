"""
Phase 26 tests: Descendant-only failure propagation and PARTIAL status reporting.
"""
import uuid
from unittest.mock import patch
import pytest

from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.schemas.execution import ExecutionResponse, ExecutionStatus
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor
from app.db.database import Base, SessionLocal, engine


def test_dag_failure_propagation_partial_status():
    """
    Graph:
      A -> C
      B (independent)

    If A fails:
    - C is marked BLOCKED (blocked_by_step_id="A").
    - B runs to completion (COMPLETED).
    - Plan ends with status PARTIAL.
    - Response answer names the failed branch.
    """
    Base.metadata.create_all(bind=engine)

    plan = SupervisorPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:8]}",
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        steps=[
            PlanStep(
                step_id="A",
                capability="text_generation",
                purpose="capability",
                depends_on=[],
                input_template={"prompt": "prompt A"},
            ),
            PlanStep(
                step_id="B",
                capability="text_generation",
                purpose="capability",
                depends_on=[],
                input_template={"prompt": "prompt B"},
            ),
            PlanStep(
                step_id="C",
                capability="text_generation",
                purpose="capability",
                depends_on=["A"],
                input_template={"prompt": "prompt C"},
            ),
        ],
    )

    executed_step_ids = []

    def fake_dispatch(db, context, capability, resolved_input, step_id):
        executed_step_ids.append(step_id)
        if step_id == "A":
            return ExecutionResponse(
                execution_id=f"exec_{step_id}",
                status=ExecutionStatus.FAILED,
                task_type=capability,
                result={"error": "Agent execution failed"},
                execution_time=0.01,
            )
        return ExecutionResponse(
            execution_id=f"exec_{step_id}",
            status=ExecutionStatus.COMPLETED,
            task_type=capability,
            result={"result": {"generated_text": f"output-{step_id}"}},
            execution_time=0.01,
        )

    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id="1",
            question="test partial graph failure",
            hitl_enabled=False,
            verification_enabled=False,
        )
        with patch(
            "app.supervisor.supervisor.supervisor_execution_router.dispatch",
            side_effect=fake_dispatch,
        ):
            res = amof_supervisor.run(db=db, context=context, preset_plan=plan)

        assert res.status == "PARTIAL"

        # A failed, B succeeded. C was never dispatched because it was blocked.
        assert "A" in executed_step_ids
        assert "B" in executed_step_ids
        assert "C" not in executed_step_ids

        step_map = {s.step_id: s for s in res.steps}
        assert step_map["A"].status == "FAILED"
        assert step_map["B"].status == "COMPLETED"
        assert step_map["C"].status == "BLOCKED"
        assert step_map["C"].blocked_by_step_id == "A"

        # Answer surfaces failed branch details
        assert "Failed branch details" in res.answer
        assert "A" in res.answer
    finally:
        db.close()
