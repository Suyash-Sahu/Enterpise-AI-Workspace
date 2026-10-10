"""
Phase 29: a step whose output fails verification must not appear on the
blackboard, and its dependents must be BLOCKED.

Driven through the real amof_supervisor.run() loop (dispatch mocked, same
pattern as tests/test_supervisor.py), with per-step verification forced on
and a database_query step whose output genuinely violates a mechanical
check (missing owner predicate) -- no verifier internals mocked.

runtime_service.generate is mocked (same pattern as
tests/test_event_publishing.py) only because the PARTIAL branch synthesizes
an answer; the mock keeps the test hermetic, it does not touch verification.
"""
import json
import uuid
from unittest.mock import patch

from app.core.config import settings
from app.db.database import Base, SessionLocal, engine
from app.schemas.execution import ExecutionResponse, ExecutionStatus
from app.schemas.runtime import RuntimeGenerateResponse
from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor


def _bad_db_output(step_id: str) -> ExecutionResponse:
    """
    A database_query result that fails RowSetVerifier: the executed SQL has
    no owner_id predicate. Everything else looks like a healthy handler
    response (nested "result" envelope, consistent row count) so the ONLY
    reason this output can be rejected is the owner-predicate check.
    """
    return ExecutionResponse(
        execution_id=f"exec_{step_id}",
        status=ExecutionStatus.COMPLETED,
        task_type="database_query",
        result={
            "result": {
                "question": "q",
                "sql": "SELECT source, chunk_count FROM ingested_documents",  # no owner predicate
                "rows": [{"source": "a.pdf", "chunk_count": 2}],
                "row_count": 1,
            },
            "provider": "postgresql",
            "model": "test-model",
        },
        execution_time=0.01,
    )


def _good_text_output(step_id: str) -> ExecutionResponse:
    return ExecutionResponse(
        execution_id=f"exec_{step_id}",
        status=ExecutionStatus.COMPLETED,
        task_type="text_generation",
        result={"result": {"generated_text": f"output-of-{step_id}"}},
        execution_time=0.01,
    )


def _run_plan(db, step2: PlanStep):
    """
    Three-step preset plan: step_1 (bad database_query output) -> step_2,
    and step_3 independent of both. Returns (response, context).
    """
    plan = SupervisorPlan(
        plan_id=f"plan_{uuid.uuid4().hex[:8]}",
        request_id=f"req_{uuid.uuid4().hex[:8]}",
        steps=[
            PlanStep(
                step_id="step_1",
                capability="database_query",
                purpose="capability",
                depends_on=[],
                input_template={"question": "$context.question", "limit": 20},
            ),
            step2,
            PlanStep(
                step_id="step_3",
                capability="text_generation",
                purpose="capability",
                depends_on=[],
                input_template={"prompt": "$context.question"},
            ),
        ],
    )

    def fake_dispatch(db, context, capability, resolved_input, step_id):
        if capability == "database_query":
            return _bad_db_output(step_id)
        return _good_text_output(step_id)

    context = SupervisorContext(
        owner_id="1",
        question="test question",
        hitl_enabled=False,
        verification_enabled=True,
    )
    mock_synth = RuntimeGenerateResponse(
        completion="Partial synthesis text.",
        provider="mock_provider",
        model="mock_model",
        runtime="local",
    )
    with patch.object(settings, "VERIFICATION_MODE", "per_step"), patch(
        "app.supervisor.supervisor.supervisor_execution_router.dispatch",
        side_effect=fake_dispatch,
    ), patch("app.execution.contracts.runtime_service.generate", return_value=mock_synth):
        res = amof_supervisor.run(db=db, context=context, preset_plan=plan)
    return res, context


def _step_rows(db, plan_id: str, step_id: str):
    from app.models.workflow import WorkflowStep

    return (
        db.query(WorkflowStep)
        .filter(WorkflowStep.plan_id == plan_id, WorkflowStep.step_id == step_id)
        .all()
    )


def test_failed_verification_result_never_reaches_blackboard():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        step2 = PlanStep(
            step_id="step_2",
            capability="text_generation",
            purpose="capability",
            depends_on=["step_1"],
            input_template={"prompt": "$state.step.step_1"},
        )
        res, context = _run_plan(db, step2)

        # step_1 completed execution but its output failed verification.
        step1 = next(s for s in res.steps if s.step_id == "step_1")
        assert step1.status == "FAILED"
        assert step1.result is None

        # The blackboard must not contain the failed output under either key
        # the writer would have used. (run_id == plan_id, set by run().)
        assert context.blackboard is not None
        assert context.blackboard.get("step.step_1") is None
    finally:
        db.close()


def test_failed_verification_persists_report_and_blocks_dependents():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        step2 = PlanStep(
            step_id="step_2",
            capability="text_generation",
            purpose="capability",
            depends_on=["step_1"],
            input_template={"prompt": "$state.step.step_1"},
        )
        res, context = _run_plan(db, step2)
        plan_id = context.blackboard.run_id

        # step_2 depended on the failed step: BLOCKED, naming step_1.
        # step_3 is independent and still completed -- failure containment,
        # not a run-wide abort.
        statuses = {s.step_id: s.status for s in res.steps}
        assert statuses["step_1"] == "FAILED"
        assert statuses["step_2"] == "BLOCKED"
        assert statuses["step_3"] == "COMPLETED"

        # The per-step report is persisted on the step row.
        rows = _step_rows(db, plan_id, "step_1")
        assert len(rows) == 1
        report = json.loads(rows[0].verification_json)
        assert report["status"] == "FAILED"
        assert any("owner_id predicate" in f for f in report["failures"])

        blocked_rows = _step_rows(db, plan_id, "step_2")
        assert len(blocked_rows) == 1
        assert blocked_rows[0].status == "BLOCKED"
        assert blocked_rows[0].blocked_by_step_id == "step_1"

        # The run as a whole is a reported partial failure, not a silent
        # success: one failed branch, one blocked dependent.
        assert res.status == "PARTIAL"
    finally:
        db.close()


def test_unverified_capability_output_reaches_blackboard_under_per_step():
    """
    text_generation has no per-step verifier (UNVERIFIED), so under per_step
    its output still reaches the blackboard -- UNVERIFIED must never block a
    step, or every capability without a checker would silently fail.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        plan = SupervisorPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            request_id=f"req_{uuid.uuid4().hex[:8]}",
            steps=[
                PlanStep(
                    step_id="step_1",
                    capability="text_generation",
                    purpose="capability",
                    depends_on=[],
                    input_template={"prompt": "$context.question"},
                ),
            ],
        )

        context = SupervisorContext(
            owner_id="1",
            question="q",
            hitl_enabled=False,
            verification_enabled=True,
        )
        with patch.object(settings, "VERIFICATION_MODE", "per_step"), patch(
            "app.supervisor.supervisor.supervisor_execution_router.dispatch",
            side_effect=lambda db, context, capability, resolved_input, step_id: _good_text_output(step_id),
        ):
            res = amof_supervisor.run(db=db, context=context, preset_plan=plan)

        assert res.status == "COMPLETED"
        assert context.blackboard.get("step.step_1") is not None
    finally:
        db.close()
