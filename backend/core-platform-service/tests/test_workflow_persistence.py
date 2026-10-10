"""
Phase 1 (AMOF-X): WorkflowPlan/WorkflowStep round-trip through the real DB.

SupervisorPlan/PlanStep (app/schemas/supervisor.py) already model a DAG
in-memory. These tests prove the persisted mirror (app/models/workflow.py)
actually survives a reload -- the entire point of this phase -- rather than
just asserting the ORM classes import cleanly.
"""
import json
import uuid

import pytest

from app.db.database import Base, SessionLocal, engine
from app.models.workflow import WorkflowPlan, WorkflowStep


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_plan_with_dependent_steps_round_trips():
    db = SessionLocal()
    owner_id = f"test_owner_{uuid.uuid4().hex[:8]}"
    try:
        plan = WorkflowPlan(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            owner_id=owner_id,
            max_steps=5,
            status="RUNNING",
        )
        db.add(plan)
        db.flush()  # assign plan.id without committing yet

        step_1 = WorkflowStep(
            plan_id=plan.id, step_id="step_1", capability="rag_search",
            depends_on_json="[]", status="COMPLETED",
        )
        step_2 = WorkflowStep(
            plan_id=plan.id, step_id="step_2", capability="database_query",
            depends_on_json="[]", status="COMPLETED",
        )
        # A real dependency edge -- the whole point of persisting this shape.
        step_3 = WorkflowStep(
            plan_id=plan.id, step_id="step_3", capability="text_generation",
            depends_on_json=json.dumps(["step_1", "step_2"]), status="PENDING",
        )
        db.add_all([step_1, step_2, step_3])
        db.commit()
        plan_id = plan.id
    finally:
        db.close()

    # Reload in a FRESH session -- proves this is a real DB round-trip, not
    # just reading back the same in-memory objects.
    db2 = SessionLocal()
    try:
        reloaded = db2.query(WorkflowPlan).filter(WorkflowPlan.id == plan_id).one()
        assert reloaded.owner_id == owner_id
        assert reloaded.status == "RUNNING"

        steps_by_id = {s.step_id: s for s in reloaded.steps}
        assert set(steps_by_id) == {"step_1", "step_2", "step_3"}

        step_3_reloaded = steps_by_id["step_3"]
        assert json.loads(step_3_reloaded.depends_on_json) == ["step_1", "step_2"]
        assert step_3_reloaded.status == "PENDING"
    finally:
        db2.close()


def test_plan_step_unique_within_plan():
    """
    ix_workflow_steps_plan_step is a unique index on (plan_id, step_id) --
    two steps in the SAME plan can't share a step_id (would make depends_on
    ambiguous). Two DIFFERENT plans reusing "step_1" is fine and expected.
    """
    db = SessionLocal()
    try:
        plan = WorkflowPlan(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            owner_id="test_owner_unique",
        )
        db.add(plan)
        db.flush()

        db.add(WorkflowStep(plan_id=plan.id, step_id="step_1", capability="rag_search"))
        db.add(WorkflowStep(plan_id=plan.id, step_id="step_1", capability="database_query"))

        with pytest.raises(Exception):
            db.commit()
    finally:
        db.rollback()
        db.close()


def test_execution_id_links_to_real_execution_table():
    """
    WorkflowStep.execution_id is a real FK to executions.id (the existing,
    already-tested per-capability-call record) -- this is deliberately NOT a
    duplicate of that table, just a pointer to it.
    """
    from sqlalchemy import inspect
    fks = {fk["referred_table"] for fk in inspect(engine).get_foreign_keys("workflow_steps")}
    assert "executions" in fks
    assert "workflow_plans" in fks
