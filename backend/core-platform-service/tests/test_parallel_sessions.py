"""
Phase 27 tests: Per-thread DB sessions and connection pool leak protection.
"""
import uuid
from unittest.mock import patch

from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.schemas.execution import ExecutionResponse, ExecutionStatus
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor
from app.db.database import Base, SessionLocal, engine


def test_parallel_execution_uses_isolated_sessions_per_thread():
    """
    Asserts that every worker thread gets its own distinct DB session instance
    and closes it, preventing connection pool leaks across runs.
    """
    Base.metadata.create_all(bind=engine)

    plan = SupervisorPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:8]}",
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        steps=[
            PlanStep(step_id="step_1", capability="text_generation", depends_on=[]),
            PlanStep(step_id="step_2", capability="text_generation", depends_on=[]),
            PlanStep(step_id="step_3", capability="text_generation", depends_on=[]),
        ],
    )

    seen_sessions = set()

    def tracking_fake_dispatch(db, context, capability, resolved_input, step_id):
        seen_sessions.add(id(db))
        return ExecutionResponse(
            execution_id=f"exec_{step_id}",
            status=ExecutionStatus.COMPLETED,
            task_type=capability,
            result={"result": {"generated_text": "ok"}},
            execution_time=0.01,
        )

    db = SessionLocal()
    main_session_id = id(db)
    try:
        context = SupervisorContext(
            owner_id="1",
            question="test session isolation",
            hitl_enabled=False,
            verification_enabled=False,
        )

        with patch(
            "app.supervisor.supervisor.supervisor_execution_router.dispatch",
            side_effect=tracking_fake_dispatch,
        ):
            res = amof_supervisor.run(db=db, context=context, preset_plan=plan)

        assert res.status == "COMPLETED"

        # Every thread must use its own session, distinct from main_session_id
        assert main_session_id not in seen_sessions
        assert len(seen_sessions) == 3

        # Verify pool stability: checked out connections must be 0 after run
        pool = engine.pool
        if hasattr(pool, "checkedout"):
            assert pool.checkedout() == 0
    finally:
        db.close()


def test_repeated_parallel_runs_do_not_leak_connections():
    """Run 5 consecutive parallel executions and verify connection pool stays stable."""
    Base.metadata.create_all(bind=engine)

    def dummy_dispatch(db, context, capability, resolved_input, step_id):
        return ExecutionResponse(
            execution_id=f"exec_{step_id}",
            status=ExecutionStatus.COMPLETED,
            task_type=capability,
            result={"result": {"generated_text": "ok"}},
            execution_time=0.01,
        )

    with patch(
        "app.supervisor.supervisor.supervisor_execution_router.dispatch",
        side_effect=dummy_dispatch,
    ):
        for _ in range(5):
            db = SessionLocal()
            try:
                plan = SupervisorPlan(
                    plan_id=f"plan_{uuid.uuid4().hex[:8]}",
                    request_id=f"req_{uuid.uuid4().hex[:8]}",
                    steps=[
                        PlanStep(step_id="s1", capability="text_generation", depends_on=[]),
                        PlanStep(step_id="s2", capability="text_generation", depends_on=[]),
                    ],
                )
                context = SupervisorContext(owner_id="1", question="leak test", hitl_enabled=False, verification_enabled=False)
                res = amof_supervisor.run(db=db, context=context, preset_plan=plan)
                assert res.status == "COMPLETED"
            finally:
                db.close()

    pool = engine.pool
    if hasattr(pool, "checkedout"):
        assert pool.checkedout() == 0
