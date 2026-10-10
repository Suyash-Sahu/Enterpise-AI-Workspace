"""
Phase 27 tests: Parallel execution of independent agents.

Covers:
- three independent steps execute concurrently under ThreadPoolExecutor;
- total wall-clock duration is measurably less than sequential execution sum;
- executed_steps and completed_steps_map retain deterministic plan order.
"""
import time
import uuid
from unittest.mock import patch

from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.schemas.execution import ExecutionResponse, ExecutionStatus
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor
from app.db.database import Base, SessionLocal, engine


def test_parallel_execution_speedup_and_plan_order_preservation():
    """
    Three independent steps with a 0.2s simulated delay each.
    Sequentially: ~0.6s total wall-clock time.
    Parallel (3 workers): ~0.2s - 0.35s total wall-clock time.
    Results merged in plan order: ["A", "B", "C"].
    """
    Base.metadata.create_all(bind=engine)

    plan = SupervisorPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:8]}",
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        steps=[
            PlanStep(step_id="A", capability="text_generation", depends_on=[]),
            PlanStep(step_id="B", capability="text_generation", depends_on=[]),
            PlanStep(step_id="C", capability="text_generation", depends_on=[]),
        ],
    )

    def slow_fake_dispatch(db, context, capability, resolved_input, step_id):
        time.sleep(0.2)  # Simulate I/O latency
        return ExecutionResponse(
            execution_id=f"exec_{step_id}",
            status=ExecutionStatus.COMPLETED,
            task_type=capability,
            result={"result": {"generated_text": f"output-{step_id}"}},
            execution_time=0.2,
        )

    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id="1",
            question="test parallel execution speedup",
            hitl_enabled=False,
            verification_enabled=False,
        )

        start = time.time()
        with patch(
            "app.supervisor.supervisor.supervisor_execution_router.dispatch",
            side_effect=slow_fake_dispatch,
        ):
            res = amof_supervisor.run(db=db, context=context, preset_plan=plan)
        elapsed = time.time() - start

        assert res.status == "COMPLETED"
        # 3 * 0.2s = 0.6s sequentially. Parallel wall-clock should be strictly < 0.5s.
        assert elapsed < 0.50, f"Expected parallel execution < 0.50s, got {elapsed:.2f}s"

        # Deterministic plan order
        executed_ids = [s.step_id for s in res.steps if s.purpose == "capability"]
        assert executed_ids == ["A", "B", "C"]
    finally:
        db.close()
