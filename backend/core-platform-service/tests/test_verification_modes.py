"""
Phase 29: VERIFICATION_MODE ablation semantics.

- "final_only" reproduces today's (pre-Phase-29) whole-answer behavior
  byte-for-byte. Mechanical proof: pre-Phase-29 behavior is exactly
  "_verify_completed_step is never called" -- no per-step report persisted,
  no step_verification_completed event, no per-step gate -- so comparing a
  final_only run against a run with _verify_completed_step patched to a
  no-op compares final_only against pre-Phase-29 behavior directly.
- "off" additionally skips the final whole-answer verifier.
- "per_step" adds per-step events/persistence/gating AND still runs the
  final verifier (it supplements, never replaces).
"""
import json
import uuid
from unittest.mock import patch

import pytest

from app.cache import client as cache_client_module
from app.core.config import settings
from app.db.database import Base, SessionLocal, engine
from app.schemas.execution import ExecutionResponse, ExecutionStatus
from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor


class _FakeRedisStream:
    """Same in-process Redis Stream stand-in as tests/test_event_publishing.py."""

    def __init__(self):
        self.entries = []
        self._counter = 0

    def xadd(self, key, fields):
        self._counter += 1
        entry_id = f"{self._counter}-0"
        self.entries.append((entry_id, dict(fields)))
        return entry_id

    def xrange(self, key, min="-", max="+", count=None):
        return self.entries


BAD_DB_RESULT = {
    "result": {
        "question": "q",
        "sql": "SELECT source FROM ingested_documents",  # fails RowSetVerifier
        "rows": [{"source": "a.pdf"}],
        "row_count": 1,
    },
    "provider": "postgresql",
    "model": "test-model",
}

GOOD_TEXT_RESULT = {"result": {"generated_text": "deterministic answer text"}}


def _scenario_db_then_text():
    """Two-step plan: database_query -> text_generation consuming $state.step.step_1."""
    return SupervisorPlan(
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
            PlanStep(
                step_id="step_2",
                capability="text_generation",
                purpose="capability",
                depends_on=["step_1"],
                input_template={"prompt": "$state.step.step_1"},
            ),
        ],
    )


def _run(db, plan, mode, *, noop_step_verifier=False):
    """
    One supervised run under the given mode, hermetic: dispatch and any LLM
    call mocked; sequential execution (parallelism is not what's under test
    and its event interleaving would be nondeterministic).
    """
    fake = _FakeRedisStream()

    def fake_dispatch(db, context, capability, resolved_input, step_id):
        if capability == "database_query":
            return ExecutionResponse(
                execution_id=f"exec_{step_id}",
                status=ExecutionStatus.COMPLETED,
                task_type=capability,
                result=BAD_DB_RESULT,
                execution_time=0.01,
            )
        return ExecutionResponse(
            execution_id=f"exec_{step_id}",
            status=ExecutionStatus.COMPLETED,
            task_type=capability,
            result=GOOD_TEXT_RESULT,
            execution_time=0.01,
        )

    context = SupervisorContext(
        owner_id="1",
        question="test question",
        hitl_enabled=False,
        verification_enabled=True,
    )
    with patch.object(cache_client_module.redis_client, "get_raw_client", lambda: fake), patch.object(
        settings, "VERIFICATION_MODE", mode
    ), patch.object(
        settings, "SUPERVISOR_PARALLEL_ENABLED", False
    ), patch(
        "app.supervisor.supervisor.supervisor_execution_router.dispatch",
        side_effect=fake_dispatch,
    ), patch(
        "app.execution.contracts.runtime_service.generate",
        return_value=None,
    ) as gen_mock:
        if noop_step_verifier:
            # Pre-Phase-29 equivalence: the per-step gate does not exist.
            gen_mock.return_value = None
            with patch(
                "app.supervisor.supervisor._verify_completed_step",
                create=True,
            ) as noop:
                noop.side_effect = lambda **kwargs: True
                res = amof_supervisor.run(db=db, context=context, preset_plan=plan)
        else:
            res = amof_supervisor.run(db=db, context=context, preset_plan=plan)
    return res, context, fake


def _observable(res):
    """Everything about a run's outcome a consumer could observe, minus volatile ids."""
    return {
        "status": res.status,
        "answer": res.answer,
        "sources": res.sources,
        "verification": res.verification,
        "approval_guard_bypassed": res.approval_guard_bypassed,
        "steps": [
            {
                "step_id": s.step_id,
                "capability": s.capability,
                "status": s.status,
                "result": s.result,
            }
            for s in sorted(res.steps, key=lambda s: s.step_id)
        ],
    }


def _events(fake):
    return [
        {"event_type": fields["event_type"], "payload": json.loads(fields["data"])["payload"]}
        for _id, fields in fake.entries
    ]


@pytest.fixture(autouse=True)
def _tables():
    Base.metadata.create_all(bind=engine)


def test_final_only_reproduces_pre_phase29_behavior_byte_for_byte():
    """
    Same scenario, same mocks: final_only vs a run where the per-step gate
    never existed. Status, answer, sources, final verification report, every
    step's status/result, and the full event stream must be identical --
    and neither run may carry step_verification_completed events or any
    verification_json.
    """
    db = SessionLocal()
    try:
        res_ref, ctx_ref, fake_ref = _run(db, _scenario_db_then_text(), "final_only", noop_step_verifier=True)
        res_final, ctx_final, fake_final = _run(db, _scenario_db_then_text(), "final_only")

        assert _observable(res_final) == _observable(res_ref)
        assert _events(fake_final) == _events(fake_ref)

        # ...and that shared behavior is pre-Phase-29 behavior: no per-step
        # events, no per-step reports, the "bad" DB output flowed onward.
        assert "step_verification_completed" not in [e["event_type"] for e in _events(fake_final)]
        from app.models.workflow import WorkflowStep

        rows = (
            db.query(WorkflowStep)
            .filter(WorkflowStep.plan_id == ctx_final.blackboard.run_id)
            .all()
        )
        assert rows and all(r.verification_json is None for r in rows)
        assert ctx_final.blackboard.get("step.step_1") is not None
    finally:
        db.close()


def test_off_skips_final_answer_verifier():
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
        res, _ctx, fake = _run(db, plan, "off")

        assert res.verification is None
        assert "verification_completed" not in [e["event_type"] for e in _events(fake)]
        assert "step_verification_completed" not in [e["event_type"] for e in _events(fake)]
        assert res.status == "COMPLETED"
    finally:
        db.close()


def test_per_step_supplements_and_still_runs_final_verifier():
    db = SessionLocal()
    try:
        # A fully successful run (good database output, owner predicate
        # present) reaches synthesis, so both gates fire: per-step reports
        # are persisted AND the whole-answer verifier still runs. Per-step
        # verification supplements the final gate; it does not replace it.
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
            ],
        )
        good_db = dict(BAD_DB_RESULT)
        good_db = {
            **BAD_DB_RESULT,
            "result": {
                **BAD_DB_RESULT["result"],
                "sql": "SELECT source FROM ingested_documents WHERE owner_id = :owner_id",
            },
        }

        def good_dispatch(db, context, capability, resolved_input, step_id):
            return ExecutionResponse(
                execution_id=f"exec_{step_id}",
                status=ExecutionStatus.COMPLETED,
                task_type=capability,
                result=good_db if capability == "database_query" else GOOD_TEXT_RESULT,
                execution_time=0.01,
            )

        context = SupervisorContext(
            owner_id="1",
            question="test question",
            hitl_enabled=False,
            verification_enabled=True,
        )
        fake = _FakeRedisStream()
        with patch.object(cache_client_module.redis_client, "get_raw_client", lambda: fake), patch.object(
            settings, "VERIFICATION_MODE", "per_step"
        ), patch.object(
            settings, "SUPERVISOR_PARALLEL_ENABLED", False
        ), patch(
            "app.supervisor.supervisor.supervisor_execution_router.dispatch",
            side_effect=good_dispatch,
        ), patch(
            "app.execution.contracts.runtime_service.generate",
            return_value=None,
        ):
            res = amof_supervisor.run(db=db, context=context, preset_plan=plan)

        assert res.status == "COMPLETED", res.answer
        event_types = [e["event_type"] for e in _events(fake)]
        assert "step_verification_completed" in event_types
        assert "verification_completed" in event_types  # final gate still ran

        from app.models.workflow import WorkflowStep

        row = (
            db.query(WorkflowStep)
            .filter(
                WorkflowStep.plan_id == context.blackboard.run_id,
                WorkflowStep.step_id == "step_1",
            )
            .first()
        )
        assert row is not None
        report = json.loads(row.verification_json)
        assert report["status"] == "PASSED"
    finally:
        db.close()


def test_final_only_still_runs_final_verifier_when_enabled():
    """
    The regression-facing half of the phase requirement: under final_only,
    a run with verification_enabled=True behaves exactly like the pre-29
    default -- the whole-answer verifier runs and reports.
    """
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
        res, _ctx, fake = _run(db, plan, "final_only")

        assert res.verification is not None
        assert res.verification["status"] in ("PASSED", "FAILED")
        assert "verification_completed" in [e["event_type"] for e in _events(fake)]
        assert res.status == "COMPLETED"
    finally:
        db.close()
