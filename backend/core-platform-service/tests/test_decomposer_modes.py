"""
Phase 28 – DECOMPOSER_MODE ablation tests.

Verifies that each of the three documented modes (off, keyword, coverage)
produces exactly the documented behaviour, and that the mode is recorded
correctly in any DecompositionAttempt rows that are written.

All LLM calls are stubbed so these tests are deterministic and require no
live Ollama/LiteLLM instance.
"""
import pytest

from app.schemas.runtime import RuntimeGenerateResponse
from app.schemas.supervisor import IntentResult
from app.supervisor import decomposer as decomposer_module
from app.supervisor.context import SupervisorContext
from app.supervisor.decomposer import task_decomposer

# ── Shared constants ──────────────────────────────────────────────────────────

INTENT_DATABASE = IntentResult(capability="database_query", confidence=0.9, reason="test")
INTENT_TEXT = IntentResult(capability="text_generation", confidence=0.9, reason="test")

# A question whose text hits both "database" and "document/search" domains.
MULTI_DOMAIN_Q = "Search the database and check the indexed documents too, then summarize."

# A question that only touches a single domain.
SINGLE_DOMAIN_Q = "How many rows are in the users table?"

# Keyword groups: hits "database_query" and "rag_search" groups → fires in keyword mode.
KEYWORD_MULTI_Q = "Search the drive and query the database together."

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


class _FakeDB:
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


def _stub(payload: str):
    return RuntimeGenerateResponse(
        completion=payload, provider="stub", model="stub", runtime="local"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Mode: "off" — decomposer must never call the LLM and always return None
# ─────────────────────────────────────────────────────────────────────────────

def test_mode_off_never_calls_llm(monkeypatch):
    monkeypatch.setattr(decomposer_module.settings, "DECOMPOSER_MODE", "off")
    calls = []
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: calls.append(req) or _stub(VALID_PLAN_JSON),
    )
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="u1", question=MULTI_DOMAIN_Q),
        intent=INTENT_DATABASE,
        db=db,
    )
    assert result is None
    assert calls == [], "mode=off must make zero LLM calls"
    assert db.added == [], "mode=off must write zero telemetry rows"


def test_mode_off_also_blocks_single_domain(monkeypatch):
    monkeypatch.setattr(decomposer_module.settings, "DECOMPOSER_MODE", "off")
    calls = []
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: calls.append(req) or _stub(VALID_PLAN_JSON),
    )
    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="u1", question=SINGLE_DOMAIN_Q),
        intent=INTENT_DATABASE,
    )
    assert result is None
    assert calls == []


# ─────────────────────────────────────────────────────────────────────────────
# Mode: "keyword" — fires only when ≥2 keyword groups match
# ─────────────────────────────────────────────────────────────────────────────

def test_mode_keyword_fires_on_multi_keyword_question(monkeypatch):
    monkeypatch.setattr(decomposer_module.settings, "DECOMPOSER_MODE", "keyword")
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: _stub(VALID_PLAN_JSON),
    )
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="u2", question=KEYWORD_MULTI_Q),
        intent=INTENT_DATABASE,
        db=db,
    )
    assert result is not None, "keyword mode should fire on multi-keyword question"
    assert len(db.added) == 1
    assert db.added[0].decomposer_mode == "keyword"
    assert db.added[0].accepted is True


def test_mode_keyword_does_not_fire_on_single_keyword_question(monkeypatch):
    monkeypatch.setattr(decomposer_module.settings, "DECOMPOSER_MODE", "keyword")
    calls = []
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: calls.append(req) or _stub(VALID_PLAN_JSON),
    )
    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="u2", question=SINGLE_DOMAIN_Q),
        intent=INTENT_DATABASE,
    )
    assert result is None
    assert calls == [], "keyword mode must not call LLM when <2 keyword groups hit"


# ─────────────────────────────────────────────────────────────────────────────
# Mode: "coverage" (default) — fires on ≥2 capability domain coverage hits
# ─────────────────────────────────────────────────────────────────────────────

def test_mode_coverage_fires_on_multi_domain_question(monkeypatch):
    monkeypatch.setattr(decomposer_module.settings, "DECOMPOSER_MODE", "coverage")
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: _stub(VALID_PLAN_JSON),
    )
    db = _FakeDB()
    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="u3", question=MULTI_DOMAIN_Q),
        intent=INTENT_DATABASE,
        db=db,
    )
    assert result is not None, "coverage mode should fire on multi-domain question"
    assert len(db.added) == 1
    assert db.added[0].decomposer_mode == "coverage"
    assert db.added[0].accepted is True


def test_mode_coverage_does_not_fire_on_single_domain(monkeypatch):
    monkeypatch.setattr(decomposer_module.settings, "DECOMPOSER_MODE", "coverage")
    calls = []
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: calls.append(req) or _stub(VALID_PLAN_JSON),
    )
    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="u3", question=SINGLE_DOMAIN_Q),
        intent=INTENT_DATABASE,
    )
    assert result is None
    assert calls == [], "coverage mode must not call LLM when only 1 domain is detected"


def test_mode_coverage_is_the_default(monkeypatch):
    """DECOMPOSER_MODE defaults to 'coverage' in settings."""
    from app.core.config import settings as real_settings
    assert real_settings.DECOMPOSER_MODE.lower() == "coverage"


# ─────────────────────────────────────────────────────────────────────────────
# Mode recorded in telemetry rows matches the active mode
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("mode", ["keyword", "coverage"])
def test_telemetry_row_records_correct_mode(monkeypatch, mode):
    monkeypatch.setattr(decomposer_module.settings, "DECOMPOSER_MODE", mode)
    monkeypatch.setattr(
        decomposer_module.runtime_service, "generate",
        lambda req: _stub(VALID_PLAN_JSON),
    )
    db = _FakeDB()
    question = KEYWORD_MULTI_Q if mode == "keyword" else MULTI_DOMAIN_Q
    task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="u4", question=question),
        intent=INTENT_DATABASE,
        db=db,
    )
    assert db.added, "at least one telemetry row should be written"
    assert db.added[0].decomposer_mode == mode
