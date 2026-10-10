"""
Phase 3 (AMOF-X): RoutingDecisionRecord round-trip & live supervisor DB persistence tests.
"""
import uuid
import pytest
from app.db.database import Base, SessionLocal, engine
from app.models.workflow import WorkflowPlan, WorkflowStep
from app.models.routing_decision import RoutingDecisionRecord
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_routing_decision_record_round_trip():
    db = SessionLocal()
    try:
        plan = WorkflowPlan(
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            owner_id="test_owner_rdec",
            status="RUNNING",
        )
        db.add(plan)
        db.flush()

        wstep = WorkflowStep(
            plan_id=plan.id,
            step_id="step_1",
            capability="text_generation",
            status="COMPLETED",
        )
        db.add(wstep)
        db.flush()

        rdec = RoutingDecisionRecord(
            workflow_step_id=wstep.id,
            placement="LOCAL",
            model="ollama/llama3",
            privacy_label="CONFIDENTIAL",
            classification_confidence=0.95,
            classification_stage="cascade_heuristic",
            predicted_quality=0.88,
            predicted_latency_ms=120.0,
            predicted_cost_usd=0.0,
            risk=0.0,
            routing_confidence=0.9,
            constraint_binding=True,
            reason="CONFIDENTIAL content forced LOCAL execution",
        )
        db.add(rdec)
        db.commit()
        rdec_id = rdec.id
    finally:
        db.close()

    db2 = SessionLocal()
    try:
        reloaded = db2.query(RoutingDecisionRecord).filter(RoutingDecisionRecord.id == rdec_id).one()
        assert reloaded.placement == "LOCAL"
        assert reloaded.model == "ollama/llama3"
        assert reloaded.privacy_label == "CONFIDENTIAL"
        assert reloaded.risk == 0.0
        assert reloaded.constraint_binding is True
        assert reloaded.step.step_id == "step_1"
    finally:
        db2.close()


def test_supervisor_run_persists_workflow_and_routing():
    from unittest.mock import patch
    from app.schemas.runtime import RuntimeGenerateResponse

    mock_resp = RuntimeGenerateResponse(
        completion="Project status overview: phase 3 completion in progress.",
        provider="mock_provider",
        model="mock_model",
        runtime="local",
        routing={
            "placement": "LOCAL",
            "model": "mock_model",
            "classification": {
                "label": "CONFIDENTIAL",
                "confidence": 0.9,
                "stage": "cascade_heuristic",
            },
            "predicted_quality": 0.85,
            "estimated_latency_ms": 50.0,
            "estimated_cost_usd": 0.0,
            "risk": 0.0,
            "routing_confidence": 0.95,
            "constraint_binding": True,
            "reason": "Test mock routing",
        },
    )

    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id="1",
            question="Write a brief project status summary.",
            hitl_enabled=False,
            verification_enabled=False,
        )
        with patch("app.execution.contracts.runtime_service.generate", return_value=mock_resp):
            res = amof_supervisor.run(db=db, context=context)
        assert res.status == "COMPLETED"

        # Query WorkflowPlan from DB
        wf_plan = db.query(WorkflowPlan).filter(WorkflowPlan.request_id == context.request_id).first()
        assert wf_plan is not None
        assert wf_plan.status == "COMPLETED"

        # Query WorkflowSteps
        wf_steps = db.query(WorkflowStep).filter(WorkflowStep.plan_id == wf_plan.id).all()
        assert len(wf_steps) > 0

        # Query RoutingDecisionRecords for text generation steps
        text_gen_steps = [s for s in wf_steps if s.capability == "text_generation"]
        if text_gen_steps:
            rdecs = db.query(RoutingDecisionRecord).filter(RoutingDecisionRecord.workflow_step_id.in_([s.id for s in text_gen_steps])).all()
            assert len(rdecs) >= 1
            for rdec in rdecs:
                assert rdec.placement in ("LOCAL", "CLOUD")
                assert rdec.privacy_label is not None
    finally:
        db.close()


def test_supervisor_run_survives_pinned_mode_with_no_routing_decision():
    """
    Regression test: TextGenerationHandler/DocumentSummaryHandler always
    include a "routing" key in their result dict, but its value is None
    whenever execution_mode is pinned rather than "auto" (no
    privacy_router.route() call happens for a pinned mode -- see
    app/runtime/policy.py::validate_request). The original persistence code
    checked `"routing" in step.result` (key presence) instead of the value,
    so this exact response -- a real, reachable shape for any pinned-mode
    text_generation call -- crashed with AttributeError on `None.get(...)`.
    """
    from unittest.mock import patch
    from app.schemas.runtime import RuntimeGenerateResponse

    mock_resp = RuntimeGenerateResponse(
        completion="A pinned-local completion with no routing decision.",
        provider="mock_provider",
        model="mock_model",
        runtime="local",
        routing=None,
    )

    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id="1",
            question="Write a brief pinned-mode summary.",
            execution_mode="local",
            hitl_enabled=False,
            verification_enabled=False,
        )
        with patch("app.execution.contracts.runtime_service.generate", return_value=mock_resp):
            res = amof_supervisor.run(db=db, context=context)
        assert res.status == "COMPLETED"

        wf_plan = db.query(WorkflowPlan).filter(WorkflowPlan.request_id == context.request_id).first()
        assert wf_plan is not None
        wf_steps = db.query(WorkflowStep).filter(WorkflowStep.plan_id == wf_plan.id).all()
        text_gen_steps = [s for s in wf_steps if s.capability == "text_generation"]
        assert text_gen_steps, "expected at least one text_generation step"

        # No routing decision should have been recorded for a pinned-mode
        # step -- there was no routing decision to record, not a crash.
        rdecs = db.query(RoutingDecisionRecord).filter(
            RoutingDecisionRecord.workflow_step_id.in_([s.id for s in text_gen_steps])
        ).all()
        assert rdecs == []
    finally:
        db.close()
