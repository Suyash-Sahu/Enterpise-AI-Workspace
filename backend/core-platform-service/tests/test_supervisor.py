import uuid
from unittest.mock import patch

import pytest
from pydantic import ValidationError
from app.schemas.supervisor import IntentResult, PlanStep, SupervisorPlan
from app.schemas.execution import ExecutionResponse, ExecutionStatus
from app.supervisor.context import SupervisorContext
from app.supervisor.policies import supervisor_policy
from app.runtime.exceptions import RuntimePolicyError


def test_supervisor_policy_allowlist():
    valid_intent = IntentResult(capability="database_query", confidence=0.95, reason="Testing")
    assert supervisor_policy.validate_intent(valid_intent) is True

    # Invalid capability is blocked by Pydantic Literal schema boundary
    with pytest.raises(ValidationError):
        IntentResult(capability="unauthorized_system_cmd", confidence=0.99, reason="Malicious")


def test_supervisor_low_confidence_clarification():
    low_conf_intent = IntentResult(capability="database_query", confidence=0.54, reason="Uncertain")
    # Low confidence returns False from policy validation
    assert supervisor_policy.validate_intent(low_conf_intent) is False


def test_supervisor_dag_cycle_rejected():
    # Construct cyclic dependency graph (step_1 -> step_2 -> step_3 -> step_1)
    step1 = PlanStep(step_id="step_1", capability="rag_search", depends_on=["step_3"])
    step2 = PlanStep(step_id="step_2", capability="database_query", depends_on=["step_1"])
    step3 = PlanStep(step_id="step_3", capability="text_generation", depends_on=["step_2"])

    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1, step2, step3])

    assert "Cyclic dependency detected" in str(exc_info.value)


def test_supervisor_unknown_dependency_rejected():
    step1 = PlanStep(step_id="step_1", capability="rag_search", depends_on=["step_nonexistent"])
    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1])

    assert "unknown dependency" in str(exc_info.value)


def test_supervisor_duplicate_step_id_rejected():
    step1 = PlanStep(step_id="step_1", capability="rag_search")
    step2 = PlanStep(step_id="step_1", capability="database_query")
    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1, step2])

    assert "Duplicate step ID" in str(exc_info.value)


def test_supervisor_max_steps_limit_rejected():
    steps = [PlanStep(step_id=f"step_{i}", capability="text_generation") for i in range(1, 7)]
    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan(steps)

    assert "exceeds maximum allowed steps" in str(exc_info.value)


def test_supervisor_dag_plan_rejects_unregistered_capability():
    """
    AMOF-X Phase 2 (ATGO): a decomposer must not be able to invent a
    capability that doesn't exist in TaskRegistry. validate_dag_plan now
    checks against the live registry instead of the hand-maintained
    ALLOWED_CAPABILITIES set this replaced -- this is the test that exercises
    that new path (every other fixture in this file already used real,
    registered capability names, so this behavior was previously untested).
    """
    step1 = PlanStep(step_id="step_1", capability="delete_all_customer_records")
    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1])

    assert "unregistered capability" in str(exc_info.value)
    assert "delete_all_customer_records" in str(exc_info.value)


# --- owner_id resolution (M17) ------------------------------------------------
# Regression cover for the silent `else 1` fallback: a non-numeric owner_id used
# to file the approval against user 1, in user 1's workspace.

def test_resolve_user_id_accepts_numeric_owner_id():
    ctx = SupervisorContext(owner_id="42", question="anything")
    assert ctx.resolve_user_id() == 42
    assert ctx.workspace_id == "ws_user_42"


def test_resolve_user_id_rejects_non_numeric_owner_id():
    ctx = SupervisorContext(owner_id="user_p7_test_owner", question="anything")

    with pytest.raises(ValueError) as exc_info:
        ctx.resolve_user_id()

    # The old behaviour: silently returns 1.
    assert "not a users.id" in str(exc_info.value)
    assert "user_p7_test_owner" in str(exc_info.value)


def test_workspace_id_cannot_diverge_from_owner():
    """The workspace is derived from the resolved id, not computed separately."""
    ctx = SupervisorContext(owner_id="nonsense", question="anything")

    with pytest.raises(ValueError):
        _ = ctx.workspace_id


# --- Phase 24: Run Blackboard / $state.<key> resolution -----------------------


def test_state_reference_resolves_end_to_end_through_supervisor_run():
    """
    A two-step preset plan where step_2's input_template references
    $state.step.step_1 -- the key every completed step is unconditionally
    written under -- must resolve to step_1's actual blackboard entry when
    driven through the real amof_supervisor.run() loop, not a standalone
    call to resolve_step_input().

    supervisor_execution_router.dispatch is mocked (not runtime_service)
    so the test exercises the real plan/blackboard/resolve_step_input wiring
    without needing a real completion or a value shaped to satisfy
    TextGenerationHandler's internal RuntimeGenerateRequest.prompt: str
    field -- $state.<key> deliberately returns whatever was stored, unlike
    $step.*, so feeding that whole object back into a strict downstream
    handler is a separate, real limitation this test does not need to paper
    over to prove resolution itself works.
    """
    from app.db.database import Base, SessionLocal, engine
    from app.supervisor.supervisor import amof_supervisor

    Base.metadata.create_all(bind=engine)

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
            PlanStep(
                step_id="step_2",
                capability="text_generation",
                purpose="capability",
                depends_on=["step_1"],
                input_template={"prompt": "$state.step.step_1"},
            ),
        ],
    )

    captured_inputs: dict[str, dict] = {}

    def fake_dispatch(db, context, capability, resolved_input, step_id):
        captured_inputs[step_id] = resolved_input
        return ExecutionResponse(
            execution_id=f"exec_{step_id}",
            status=ExecutionStatus.COMPLETED,
            task_type=capability,
            result={"result": {"generated_text": f"output-of-{step_id}"}},
            execution_time=0.01,
        )

    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id="1",
            question="test question",
            hitl_enabled=False,
            verification_enabled=False,
        )
        with patch(
            "app.supervisor.supervisor.supervisor_execution_router.dispatch",
            side_effect=fake_dispatch,
        ):
            res = amof_supervisor.run(db=db, context=context, preset_plan=plan)

        assert res.status == "COMPLETED"

        step2_prompt = captured_inputs["step_2"]["prompt"]
        assert step2_prompt is not None
        # The blackboard's stored shape (AgentResult.output == the raw step
        # result dict), not the $step. branch's narrowed `.result` value --
        # proof this went through RunBlackboard.get(), not the existing
        # $step. branch.
        assert step2_prompt["output"] == {"result": {"generated_text": "output-of-step_1"}}

        assert context.blackboard is not None
        assert context.blackboard.get("step.step_1") == step2_prompt
    finally:
        db.close()


def test_state_reference_resolves_to_none_when_key_never_written():
    """Fail-closed: an unknown $state.<key> resolves to None, never raises."""
    from app.supervisor.blackboard import RunBlackboard
    from app.supervisor.planner import supervisor_planner
    from app.db.database import Base, SessionLocal, engine

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        context = SupervisorContext(owner_id="1", question="q")
        context.blackboard = RunBlackboard(db=db, run_id=f"run_{uuid.uuid4().hex[:8]}", owner_id="1")

        step = PlanStep(step_id="step_1", capability="text_generation", input_template={"prompt": "$state.nope"})
        resolved = supervisor_planner.resolve_step_input(step=step, context=context, completed_steps={})
        assert resolved["prompt"] is None
    finally:
        db.close()


def test_state_reference_resolves_to_none_when_no_blackboard_attached():
    """
    A legacy caller that builds a SupervisorContext directly (never sets
    .blackboard) must not crash resolve_step_input -- $state.* fails closed
    to None exactly like $step.* does for a missing dependency.
    """
    from app.supervisor.planner import supervisor_planner

    context = SupervisorContext(owner_id="1", question="q")
    assert context.blackboard is None

    step = PlanStep(step_id="step_1", capability="text_generation", input_template={"prompt": "$state.anything"})
    resolved = supervisor_planner.resolve_step_input(step=step, context=context, completed_steps={})
    assert resolved["prompt"] is None


def test_existing_reference_forms_unchanged_alongside_state():
    """
    $context.question, $context.file_id and $step.X.result must keep working
    byte-identically now that a fourth form exists in the same allowlist.
    """
    from app.supervisor.planner import supervisor_planner

    dep = PlanStep(step_id="step_1", capability="rag_search", result={"result": {"answer": "42"}})
    step = PlanStep(
        step_id="step_2",
        capability="text_generation",
        input_template={
            "a": "$context.question",
            "b": "$context.file_id",
            "c": "$step.step_1.result",
        },
    )
    context = SupervisorContext(owner_id="1", question="the question", file_id="file_abc")
    resolved = supervisor_planner.resolve_step_input(
        step=step, context=context, completed_steps={"step_1": dep}
    )
    assert resolved == {"a": "the question", "b": "file_abc", "c": {"answer": "42"}}


def test_capability_agent_map_wires_writes_state_when_populated():
    """
    Unit-level proof that the writes_state hook fires: InboxAgent (the one
    Phase 23 agent with a non-empty writes_state=["inbox_findings"]) is
    mapped from inbox.classify/inbox.draft_reply in
    app.supervisor.supervisor.CAPABILITY_AGENT_MAP. A completed step for
    that capability must therefore write BOTH step.<step_id> and
    inbox_findings.
    """
    from app.supervisor.blackboard import RunBlackboard
    from app.supervisor.supervisor import _write_step_to_blackboard, CAPABILITY_AGENT_MAP
    from app.db.database import Base, SessionLocal, engine

    assert CAPABILITY_AGENT_MAP.get("inbox.classify") == "InboxAgent"

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        context = SupervisorContext(owner_id="1", question="q")
        context.blackboard = RunBlackboard(db=db, run_id=f"run_{uuid.uuid4().hex[:8]}", owner_id="1")

        _write_step_to_blackboard(
            context, "step_1", "inbox.classify", {"result": {"classifications": [], "counts": {}}}
        )

        assert context.blackboard.get("step.step_1") is not None
        assert context.blackboard.get("inbox_findings") is not None
        assert context.blackboard.get("inbox_findings")["output"] == {
            "result": {"classifications": [], "counts": {}}
        }
    finally:
        db.close()
