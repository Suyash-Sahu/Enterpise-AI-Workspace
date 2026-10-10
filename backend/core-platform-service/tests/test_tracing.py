"""
AMOF-X Phase 10 Observability Tests: TraceView Aggregation & API.

Verifies end-to-end aggregation of workflow plans, routing decisions, replanning events,
executions, and approvals by trace_id.
"""
import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, engine
from app.models.user import User
from app.models.role import Role
from app.models.workflow import WorkflowPlan, WorkflowStep, ReplanningEvent
from app.models.routing_decision import RoutingDecisionRecord
from app.models.execution import Execution
from app.models.approval import Approval
from app.db.seed import seed_roles
from app.observability.tracing import trace_view_service

OWNER_ID = "1"
# Unique per run: this suite runs against the real dev Postgres database with
# no per-test rollback, so a fixed id accumulates rows across repeated runs
# and get_trace's request_id lookup (legitimately not unique -- a real plan
# can share a request_id with other executions) picks all of them up.
TRACE_ID = f"test_trace_{uuid.uuid4().hex[:12]}"


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_roles(db)
        role = db.query(Role).filter(Role.name == "user").first()
        if not db.query(User).filter(User.id == int(OWNER_ID)).first():
            db.add(User(id=int(OWNER_ID), name="Trace User", email="trace_user@example.com", password_hash="hash", role_id=role.id))
        db.commit()
    finally:
        db.close()
    yield


def test_trace_view_aggregation():
    """
    Constructs a complete trace lifecycle (Plan -> Step -> RoutingDecision -> Execution -> Approval)
    and verifies that trace_view_service.get_trace retrieves all correlated entities.
    """
    db = SessionLocal()
    try:
        # Create WorkflowPlan
        plan = WorkflowPlan(
            request_id=TRACE_ID,
            owner_id=OWNER_ID,
            status="COMPLETED",
            max_steps=5,
        )
        db.add(plan)
        db.commit()
        db.refresh(plan)

        # Create WorkflowStep
        step = WorkflowStep(
            plan_id=plan.id,
            step_id="step_1",
            capability="text_generation",
            depends_on_json="[]",
            status="COMPLETED",
            execution_time=0.45,
        )
        db.add(step)
        db.commit()
        db.refresh(step)

        # Create RoutingDecisionRecord
        rd = RoutingDecisionRecord(
            workflow_step_id=step.id,
            placement="LOCAL",
            model="ollama/qwen2.5:7b",
            privacy_label="INTERNAL",
            classification_confidence=0.98,
            predicted_quality=0.85,
            predicted_latency_ms=450.0,
            predicted_cost_usd=0.0,
            routing_confidence=0.95,
            reason="Local model selected for internal classification",
        )
        db.add(rd)

        # Create Execution
        exec_row = Execution(
            owner_id=OWNER_ID,
            request_id=TRACE_ID,
            task_type="text_generation",
            status="COMPLETED",
            provider="ollama",
            model="qwen2.5:7b",
            execution_time=0.45,
        )
        db.add(exec_row)
        db.commit()
        db.refresh(exec_row)

        step.execution_id = exec_row.id
        db.commit()

        # Query trace_view_service
        trace = trace_view_service.get_trace(db=db, trace_id=TRACE_ID, owner_id=OWNER_ID)

        assert trace.trace_id == TRACE_ID
        assert trace.owner_id == OWNER_ID
        assert trace.plan is not None
        assert trace.plan.plan_id == plan.id
        assert len(trace.plan.steps) == 1
        assert trace.plan.steps[0].step_id == "step_1"

        assert len(trace.routing_decisions) == 1
        assert trace.routing_decisions[0].placement == "LOCAL"
        assert trace.routing_decisions[0].model == "ollama/qwen2.5:7b"

        assert len(trace.executions) == 1
        assert trace.executions[0].execution_id == exec_row.id
        assert trace.total_latency_ms > 0

    finally:
        db.close()
