"""
Phase 4 (AMOF-X): CDRP (Confidence-Driven Dynamic Replanning) unit & integration tests.
"""
import uuid
import pytest

from app.db.database import Base, SessionLocal, engine
from app.models.workflow import WorkflowPlan, WorkflowStep, ReplanningEvent
from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.supervisor.context import SupervisorContext
from app.supervisor.verifier import VerificationReport, response_verifier
from app.supervisor.replanner import cdrp_replanner
from app.supervisor.supervisor import amof_supervisor


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_verifier_confidence_bands():
    # 1. Critical: degenerate output
    rep_crit = response_verifier.verify(answer="", aggregated_data={}, sources=[])
    assert rep_crit.confidence_band == "critical"

    # 2. Low: failed verification check (contradicting row count).
    # "100 rows" (digit directly before "rows") is what
    # ResponseVerifier._check_row_counts's positive_claim regex matches --
    # "100 matching rows" (an adjective in between) does not, which made
    # this fixture assert PASSED/high instead of the intended FAILED/low.
    rep_low = response_verifier.verify(
        answer="We found 100 rows in the database.",
        aggregated_data={
            "step_1": {
                "capability": "database_query",
                "output": {"rows": [], "row_count": 0},
            }
        },
        sources=[],
    )
    assert rep_low.confidence_band == "low"

    # 3. High: passed and confidence >= 0.85
    rep_high = response_verifier.verify(
        answer="The project architecture uses FastAPI and Next.js.",
        aggregated_data={},
        sources=[],
    )
    assert rep_high.confidence_band in ("high", "medium")


def test_cdrp_replanner_medium_band_widens_parameters():
    db = SessionLocal()
    try:
        plan = SupervisorPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            request_id="req_test_med",
            steps=[
                PlanStep(
                    step_id="step_1",
                    capability="rag_search",
                    purpose="capability",
                    depends_on=[],
                    input_template={"query": "test query", "top_k": 5},
                )
            ],
        )

        wf_plan = WorkflowPlan(
            id=plan.plan_id,
            request_id=plan.request_id,
            owner_id="1",
            status="RUNNING",
        )
        db.add(wf_plan)

        orig_wf_step = WorkflowStep(
            plan_id=plan.plan_id,
            step_id="step_1",
            capability="rag_search",
            status="COMPLETED",
        )
        db.add(orig_wf_step)
        db.commit()

        context = SupervisorContext(owner_id="1", question="test query")
        report = VerificationReport(
            status="PASSED",
            confidence=0.60,
            checks={"non_degenerate": True},
            failures=[],
        )

        new_step, event = cdrp_replanner.replan(
            db=db,
            context=context,
            plan=plan,
            failed_step=plan.steps[0],
            report=report,
            replan_count=0,
            original_workflow_step_id=orig_wf_step.id,
        )

        assert new_step is not None
        assert new_step.capability == "rag_search"
        assert new_step.input_template.get("top_k") == 10
        assert event is not None
        assert "Medium confidence" in event.reason
    finally:
        db.close()


def test_cdrp_replanner_low_band_capability_substitution():
    db = SessionLocal()
    try:
        plan = SupervisorPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            request_id="req_test_low",
            steps=[
                PlanStep(
                    step_id="step_1",
                    capability="rag_search",
                    purpose="capability",
                    depends_on=[],
                    input_template={"query": "test query"},
                )
            ],
        )

        wf_plan = WorkflowPlan(
            id=plan.plan_id,
            request_id=plan.request_id,
            owner_id="1",
            status="RUNNING",
        )
        db.add(wf_plan)

        orig_wf_step = WorkflowStep(
            plan_id=plan.plan_id,
            step_id="step_1",
            capability="rag_search",
            status="FAILED",
        )
        db.add(orig_wf_step)
        db.commit()

        context = SupervisorContext(owner_id="1", question="test query")
        report = VerificationReport(
            status="FAILED",
            confidence=0.40,
            checks={"non_degenerate": True},
            failures=["Grounding check failed"],
        )

        new_step, event = cdrp_replanner.replan(
            db=db,
            context=context,
            plan=plan,
            failed_step=plan.steps[0],
            report=report,
            replan_count=0,
            original_workflow_step_id=orig_wf_step.id,
        )

        assert new_step is not None
        assert new_step.capability == "rag_answer"
        assert event is not None
        assert "Low confidence" in event.reason

        # Regression: capability substitution must translate the input
        # schema, not carry the old capability's keys over verbatim.
        # rag_search reads "query"; rag_answer reads "question" -- a
        # verbatim copy of {"query": "test query"} leaves rag_answer's
        # handler reading input_data.get("question", "") and getting "",
        # silently turning the "recovery" into a step that runs on empty
        # input instead of the real question.
        assert "question" in new_step.input_template
        assert new_step.input_template["question"] == "$context.question"
        assert "query" not in new_step.input_template
    finally:
        db.close()


def test_cdrp_replanning_cap_enforced():
    db = SessionLocal()
    try:
        plan = SupervisorPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            request_id="req_test_cap",
            steps=[
                PlanStep(
                    step_id="step_1",
                    capability="rag_search",
                    purpose="capability",
                    depends_on=[],
                    input_template={"query": "test query", "top_k": 5},
                )
            ],
        )

        wf_plan = WorkflowPlan(
            id=plan.plan_id,
            request_id=plan.request_id,
            owner_id="1",
            status="RUNNING",
        )
        db.add(wf_plan)

        orig_wf_step = WorkflowStep(
            plan_id=plan.plan_id,
            step_id="step_1",
            capability="rag_search",
            status="COMPLETED",
        )
        db.add(orig_wf_step)
        db.commit()

        context = SupervisorContext(owner_id="1", question="test query")
        report = VerificationReport(
            status="PASSED",
            confidence=0.60,
            checks={"non_degenerate": True},
            failures=[],
        )

        # Max replans set to 2, attempt with replan_count=2
        new_step, event = cdrp_replanner.replan(
            db=db,
            context=context,
            plan=plan,
            failed_step=plan.steps[0],
            report=report,
            replan_count=2,
            original_workflow_step_id=orig_wf_step.id,
        )

        assert new_step is None
        assert event is not None
        assert "cap exceeded" in event.reason
    finally:
        db.close()


def test_replanned_side_effecting_step_requires_approval():
    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id="1",
            question="send an email notice to user",
            hitl_enabled=True,
            verification_enabled=False,
        )
        res = amof_supervisor.run(db=db, context=context)
        assert res.status == "WAITING_FOR_APPROVAL"
        assert res.approval_id is not None
    finally:
        db.close()


def test_cdrp_low_band_does_not_ping_pong_rag_answer_and_text_generation():
    """
    Direct regression for docs/phases/PHASE_10.md section 6b: rag_answer's
    low-band substitution used to always pick text_generation, and
    text_generation's always picked rag_answer straight back -- an infinite
    2-cycle bounded only by hitting CDRP_MAX_REPLANS, not by convergence.
    Threading `tried_capabilities` (as app/supervisor/supervisor.py's
    verification loop now does across iterations) must prevent the second
    hop from returning to rag_answer.
    """
    db = SessionLocal()
    try:
        plan = SupervisorPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            request_id="req_test_pingpong",
            steps=[
                PlanStep(
                    step_id="step_1",
                    capability="rag_answer",
                    purpose="capability",
                    depends_on=[],
                    input_template={"question": "test query"},
                )
            ],
        )
        wf_plan = WorkflowPlan(id=plan.plan_id, request_id=plan.request_id, owner_id="1", status="RUNNING")
        db.add(wf_plan)
        orig_wf_step = WorkflowStep(plan_id=plan.plan_id, step_id="step_1", capability="rag_answer", status="FAILED")
        db.add(orig_wf_step)
        db.commit()

        context = SupervisorContext(owner_id="1", question="test query")
        report = VerificationReport(status="FAILED", confidence=0.40, checks={}, failures=["low confidence"])

        tried = {"rag_answer"}
        step_1_replan, _ = cdrp_replanner.replan(
            db=db,
            context=context,
            plan=plan,
            failed_step=plan.steps[0],
            report=report,
            replan_count=0,
            original_workflow_step_id=orig_wf_step.id,
            tried_capabilities=tried,
        )
        assert step_1_replan is not None
        assert step_1_replan.capability == "text_generation"
        tried.add("text_generation")

        step_2_replan, event_2 = cdrp_replanner.replan(
            db=db,
            context=context,
            plan=plan,
            failed_step=step_1_replan,
            report=report,
            replan_count=1,
            original_workflow_step_id=orig_wf_step.id,
            tried_capabilities=tried,
        )
        assert step_2_replan is not None
        assert step_2_replan.capability != "rag_answer"
        assert step_2_replan.capability != "text_generation"
    finally:
        db.close()


def test_cdrp_low_band_oscillation_resolved_no_repeated_capability(monkeypatch):
    """
    Reproduces the exact 5-step oscillation chain observed in the Phase 10
    smoke run (docs/phases/PHASE_10.md section 6b):
    text_generation -> rag_search -> text_generation -> rag_answer ->
    text_generation, which previously never converged and was bounded only
    by CDRP_MAX_REPLANS. Drives repeated low-band substitutions the way
    app/supervisor/supervisor.py's verification loop does (threading
    tried_capabilities across iterations) and asserts every capability in
    the chain is distinct, terminating in either a stable capability or an
    explicit critical/human-escalation outcome -- never a repeat.
    """
    monkeypatch.setattr(
        "app.supervisor.replanner.task_registry.list_supported_tasks",
        lambda: ["rag_search", "rag_answer", "database_query", "text_generation"],
    )

    db = SessionLocal()
    try:
        plan = SupervisorPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            request_id="req_test_osc",
            steps=[
                PlanStep(
                    step_id="step_1",
                    capability="text_generation",
                    purpose="capability",
                    depends_on=[],
                    input_template={"prompt": "test query"},
                )
            ],
        )
        wf_plan = WorkflowPlan(id=plan.plan_id, request_id=plan.request_id, owner_id="1", status="RUNNING")
        db.add(wf_plan)
        orig_wf_step = WorkflowStep(plan_id=plan.plan_id, step_id="step_1", capability="text_generation", status="FAILED")
        db.add(orig_wf_step)
        db.commit()

        context = SupervisorContext(owner_id="1", question="test query")
        report = VerificationReport(status="FAILED", confidence=0.40, checks={}, failures=["low confidence"])

        failed_step = plan.steps[0]
        tried_capabilities: set[str] = set()
        capability_sequence = [failed_step.capability]

        for _ in range(10):  # generous bound -- must terminate well before this
            tried_capabilities.add(failed_step.capability)
            new_step, event = cdrp_replanner.replan(
                db=db,
                context=context,
                plan=plan,
                failed_step=failed_step,
                report=report,
                replan_count=0,  # isolates substitution logic from the cap, which has its own test
                original_workflow_step_id=orig_wf_step.id,
                tried_capabilities=tried_capabilities,
            )
            if new_step is None:
                # Exhausted every alternative capability -> explicit human
                # escalation, never a silent stall or a repeated capability.
                assert event is not None
                assert "critical" in event.reason.lower() or "escalation" in event.reason.lower()
                break
            assert new_step.capability not in capability_sequence, (
                f"capability '{new_step.capability}' was revisited -- oscillation reintroduced: {capability_sequence}"
            )
            capability_sequence.append(new_step.capability)
            tried_capabilities.add(new_step.capability)
            failed_step = new_step
        else:
            pytest.fail("replanning never terminated within 10 substitutions")

        assert capability_sequence[0] == "text_generation"
        assert len(capability_sequence) == len(set(capability_sequence))
        # All 4 registered capabilities were tried exactly once before
        # exhaustion forced the critical/human-escalation outcome.
        assert len(capability_sequence) == 4
    finally:
        db.close()


def test_cdrp_low_band_fallback_is_deterministic_not_registration_order(monkeypatch):
    """
    Regression for docs/phases/PHASE_10.md section 6b finding 3: for a
    capability with no explicit substitution preference, the fallback used
    to pick "the first different capability in registry order" -- an
    accident of ExecutionRegistry._register_default_capabilities()'s call
    order, not a deliberate choice. Registration order below is deliberately
    NOT alphabetical, so the two would disagree if that old behavior
    returned.
    """
    monkeypatch.setattr(
        "app.supervisor.replanner.task_registry.list_supported_tasks",
        lambda: ["zzz_custom", "database_query", "rag_answer"],
    )

    db = SessionLocal()
    try:
        plan = SupervisorPlan(
            plan_id=f"plan_{uuid.uuid4().hex[:8]}",
            request_id="req_test_fallback",
            steps=[
                PlanStep(
                    step_id="step_1",
                    capability="unmapped_capability",
                    purpose="capability",
                    depends_on=[],
                    input_template={},
                )
            ],
        )
        wf_plan = WorkflowPlan(id=plan.plan_id, request_id=plan.request_id, owner_id="1", status="RUNNING")
        db.add(wf_plan)
        orig_wf_step = WorkflowStep(plan_id=plan.plan_id, step_id="step_1", capability="unmapped_capability", status="FAILED")
        db.add(orig_wf_step)
        db.commit()

        context = SupervisorContext(owner_id="1", question="test query")
        report = VerificationReport(status="FAILED", confidence=0.40, checks={}, failures=["low confidence"])

        new_step, event = cdrp_replanner.replan(
            db=db,
            context=context,
            plan=plan,
            failed_step=plan.steps[0],
            report=report,
            replan_count=0,
            original_workflow_step_id=orig_wf_step.id,
        )

        assert new_step is not None
        # Alphabetically first among the registered options -- not
        # "zzz_custom", which registration order would have returned first.
        assert new_step.capability == "database_query"
    finally:
        db.close()
