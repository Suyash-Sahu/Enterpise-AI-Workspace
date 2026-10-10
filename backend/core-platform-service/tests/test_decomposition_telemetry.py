"""
Phase 28 – DecompositionAttempt telemetry tests.

Every rejection path must write a DecompositionAttempt row with the correct
`accepted` boolean, `attempt_number`, and `rejection_reason` string.
Accepted plans must also write a row with accepted=True and no reason.

The database session is faked with a simple accumulator so the tests are
fully in-memory and don't require a live Postgres instance.
"""
import pytest

from app.schemas.runtime import RuntimeGenerateResponse
from app.schemas.supervisor import IntentResult
from app.supervisor import decomposer as decomposer_module
from app.supervisor.context import SupervisorContext
from app.supervisor.decomposer import task_decomposer

INTENT = IntentResult(capability="text_generation", confidence=0.9, reason="test")

# ── Multi-domain question that the coverage gate accepts ──────────────────────
MULTI_DOMAIN_Q = "Search the database and check the Drive documents, then summarize."

VALID_PLAN_JSON = (
    '{"steps": ['
    '{"step_id": "step_1", "capability": "database_query", "depends_on": [], '
    '"input_template": {"question": "$context.question"}}, '
    '{"step_id": "step_2", "capability": "rag_search", "depends_on": [], '
    '"input_template": {"query": "$context.question"}}, '
    '{"step_id": "step_3", "capability": "text_generation", "depends_on": ["step_1", "step_2"], '
    '"input_template": {"prompt": "$step.step_1.result"}}'
    ']}'
)

INVALID_JSON = "this is not json"

HALLUCINATED_JSON = (
    '{"steps": ['
    '{"step_id": "step_1", "capability": "delete_everything", "depends_on": []}, '
    '{"step_id": "step_2", "capability": "rag_search", "depends_on": []}'
    ']}'
)

CYCLIC_JSON = (
    '{"steps": ['
    '{"step_id": "step_1", "capability": "database_query", "depends_on": ["step_2"]}, '
    '{"step_id": "step_2", "capability": "rag_search", "depends_on": ["step_1"]}'
    ']}'
)

UNDER_LENGTH_JSON = (
    '{"steps": ['
    '{"step_id": "step_1", "capability": "database_query", "depends_on": []}'
    ']}'
)


class _FakeDB:
    """Accumulates added objects without touching a real database."""

    def __init__(self):
        self.added: list = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


def _ctx() -> SupervisorContext:
    return SupervisorContext(owner_id="tel-owner-1", question=MULTI_DOMAIN_Q)


# ─────────────────────────────────────────────────────────────────────────────
# Accepted plan: attempt 1 accepted=True, no rejection_reason
# ─────────────────────────────────────────────────────────────────────────────

def test_accepted_plan_writes_one_row_with_accepted_true(monkeypatch):
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: RuntimeGenerateResponse(
            completion=VALID_PLAN_JSON, provider="stub", model="stub", runtime="local"
        ),
    )
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(context=_ctx(), intent=INTENT, db=db)

    assert result is not None, "expected a valid plan"
    rows = db.added
    assert len(rows) == 1
    row = rows[0]
    assert row.accepted is True
    assert row.attempt_number == 1
    assert row.rejection_reason is None
    assert row.decomposer_mode in ("coverage", "keyword")


# ─────────────────────────────────────────────────────────────────────────────
# Unparseable LLM output: attempt 1 rejected, repair also fails → 2 rows
# ─────────────────────────────────────────────────────────────────────────────

def test_unparseable_output_writes_two_rejection_rows(monkeypatch):
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: RuntimeGenerateResponse(
            completion=INVALID_JSON, provider="stub", model="stub", runtime="local"
        ),
    )
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(context=_ctx(), intent=INTENT, db=db)

    assert result is None
    rows = db.added
    assert len(rows) == 2

    r1, r2 = rows
    assert r1.attempt_number == 1
    assert r1.accepted is False
    assert "unparseable" in r1.rejection_reason.lower()

    assert r2.attempt_number == 2
    assert r2.accepted is False
    assert r2.rejection_reason is not None


# ─────────────────────────────────────────────────────────────────────────────
# Hallucinated capability: both attempts receive the same bad plan → 2 rows
# ─────────────────────────────────────────────────────────────────────────────

def test_hallucinated_capability_writes_rejection_row(monkeypatch):
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: RuntimeGenerateResponse(
            completion=HALLUCINATED_JSON, provider="stub", model="stub", runtime="local"
        ),
    )
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(context=_ctx(), intent=INTENT, db=db)

    assert result is None
    rows = db.added
    assert len(rows) == 2
    assert all(r.accepted is False for r in rows)
    # The first rejection must mention the capability policy
    assert rows[0].rejection_reason is not None


# ─────────────────────────────────────────────────────────────────────────────
# Cyclic plan: rejected at policy gate
# ─────────────────────────────────────────────────────────────────────────────

def test_cyclic_plan_rejection_is_recorded(monkeypatch):
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: RuntimeGenerateResponse(
            completion=CYCLIC_JSON, provider="stub", model="stub", runtime="local"
        ),
    )
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(context=_ctx(), intent=INTENT, db=db)

    assert result is None
    rows = db.added
    assert len(rows) == 2
    assert rows[0].accepted is False
    assert rows[0].rejection_reason is not None


# ─────────────────────────────────────────────────────────────────────────────
# Under-length plan (< 2 steps): rejected
# ─────────────────────────────────────────────────────────────────────────────

def test_under_length_plan_rejection_is_recorded(monkeypatch):
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: RuntimeGenerateResponse(
            completion=UNDER_LENGTH_JSON, provider="stub", model="stub", runtime="local"
        ),
    )
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(context=_ctx(), intent=INTENT, db=db)

    assert result is None
    rows = db.added
    assert len(rows) == 2
    assert "under-length" in rows[0].rejection_reason.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Repair pass succeeds on attempt 2: 2 rows, attempt 1 rejected, attempt 2 accepted
# ─────────────────────────────────────────────────────────────────────────────

def test_repair_pass_success_writes_two_rows_second_accepted(monkeypatch):
    call_count = [0]

    def _gen(req):
        call_count[0] += 1
        payload = INVALID_JSON if call_count[0] == 1 else VALID_PLAN_JSON
        return RuntimeGenerateResponse(
            completion=payload, provider="stub", model="stub", runtime="local"
        )

    monkeypatch.setattr(decomposer_module.runtime_service, "generate", _gen)
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(context=_ctx(), intent=INTENT, db=db)

    assert result is not None, "repair pass should have produced a valid plan"
    rows = db.added
    assert len(rows) == 2
    assert rows[0].attempt_number == 1
    assert rows[0].accepted is False
    assert rows[1].attempt_number == 2
    assert rows[1].accepted is True
    assert rows[1].rejection_reason is None


# ─────────────────────────────────────────────────────────────────────────────
# Repair fires at most once: call count must be exactly 2
# ─────────────────────────────────────────────────────────────────────────────

def test_repair_pass_fires_at_most_once(monkeypatch):
    call_count = [0]

    def _gen(req):
        call_count[0] += 1
        return RuntimeGenerateResponse(
            completion=INVALID_JSON, provider="stub", model="stub", runtime="local"
        )

    monkeypatch.setattr(decomposer_module.runtime_service, "generate", _gen)
    db = _FakeDB()
    task_decomposer.maybe_decompose(context=_ctx(), intent=INTENT, db=db)

    assert call_count[0] == 2, f"Expected exactly 2 LLM calls (1 initial + 1 repair), got {call_count[0]}"
