"""
Tests for the ATGO decomposer (app/supervisor/decomposer.py) -- the
remaining Phase 2 deliverable: turning a multi-source objective into a real,
validated multi-node DAG instead of the fixed planner's single step.

The LLM call is stubbed via monkeypatch so these are deterministic and don't
depend on a live Ollama/LiteLLM runtime being reachable -- the same
uncertainty test_supervisor.py's policy tests already avoid by not touching
the runtime layer at all. test_supervisor_integration.py separately covers
the real end-to-end runtime path for the fixed planner's capabilities.
"""
import pytest

from app.schemas.runtime import RuntimeGenerateResponse
from app.supervisor import decomposer as decomposer_module
from app.supervisor.context import SupervisorContext
from app.supervisor.decomposer import DECOMPOSER_VERSION, task_decomposer
from app.schemas.supervisor import IntentResult

INTENT = IntentResult(capability="text_generation", confidence=0.9, reason="test")


def _stub_response(completion: str) -> RuntimeGenerateResponse:
    return RuntimeGenerateResponse(
        completion=completion, provider="stub", model="stub", runtime="local",
    )


def test_single_source_query_never_calls_the_decomposer(monkeypatch):
    calls = []
    monkeypatch.setattr(decomposer_module.runtime_service, "generate", lambda req: calls.append(req) or _stub_response(""))

    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="42", question="Summarize this document for me."),
        intent=INTENT,
    )

    assert result is None
    assert calls == []


def test_multi_source_query_produces_a_real_multi_node_graph(monkeypatch):
    valid_json = (
        '{"steps": ['
        '{"step_id": "step_1", "capability": "database_query", "depends_on": [], '
        '"input_template": {"question": "$context.question"}}, '
        '{"step_id": "step_2", "capability": "rag_search", "depends_on": [], '
        '"input_template": {"query": "$context.question"}}, '
        '{"step_id": "step_3", "capability": "text_generation", "depends_on": ["step_1", "step_2"], '
        '"input_template": {"prompt": "$step.step_1.result"}}'
        ']}'
    )
    monkeypatch.setattr(decomposer_module.runtime_service, "generate", lambda req: _stub_response(valid_json))

    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="42", question="Check the database and search Drive, then combine the results."),
        intent=INTENT,
    )

    assert result is not None
    assert len(result) == 3
    merge_step = next(s for s in result if s.step_id == "step_3")
    assert set(merge_step.depends_on) == {"step_1", "step_2"}
    assert merge_step.purpose == "synthesis"


def test_hallucinated_capability_is_rejected(monkeypatch):
    invalid_json = (
        '{"steps": ['
        '{"step_id": "step_1", "capability": "delete_all_records", "depends_on": []}, '
        '{"step_id": "step_2", "capability": "rag_search", "depends_on": []}'
        ']}'
    )
    monkeypatch.setattr(decomposer_module.runtime_service, "generate", lambda req: _stub_response(invalid_json))

    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="42", question="Check the database and search Drive for this."),
        intent=INTENT,
    )

    assert result is None


def test_cyclic_graph_is_rejected(monkeypatch):
    cyclic_json = (
        '{"steps": ['
        '{"step_id": "step_1", "capability": "database_query", "depends_on": ["step_2"]}, '
        '{"step_id": "step_2", "capability": "rag_search", "depends_on": ["step_1"]}'
        ']}'
    )
    monkeypatch.setattr(decomposer_module.runtime_service, "generate", lambda req: _stub_response(cyclic_json))

    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="42", question="Check the database and search Drive for this."),
        intent=INTENT,
    )

    assert result is None


def test_malformed_llm_output_falls_back_gracefully(monkeypatch):
    monkeypatch.setattr(decomposer_module.runtime_service, "generate", lambda req: _stub_response("not json at all"))

    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="42", question="Check the database and search Drive for this."),
        intent=INTENT,
    )

    assert result is None


def test_decomposer_version_is_a_stable_tag():
    assert isinstance(DECOMPOSER_VERSION, str) and DECOMPOSER_VERSION


def test_llm_plan_with_invalid_input_binding_is_rejected(monkeypatch):
    """
    Phase 25: an LLM-produced plan can name an input_bindings reference to a
    producer field that doesn't exist on the declared output schema, exactly
    like it can hallucinate a capability (test_hallucinated_capability_is_rejected
    above) -- both are rejected by the same supervisor_policy.validate_dag_plan
    gate the decomposer re-validates through, and the decomposer falls back
    to None rather than surfacing the rejection.
    """
    invalid_binding_json = (
        '{"steps": ['
        '{"step_id": "step_1", "capability": "database_query", "depends_on": [], '
        '"input_template": {"question": "$context.question"}}, '
        '{"step_id": "step_2", "capability": "database_query", "depends_on": ["step_1"], '
        '"input_template": {"question": "$context.question"}, '
        '"input_bindings": {"question": "$step.step_1.output.not_a_real_field"}}'
        ']}'
    )
    monkeypatch.setattr(decomposer_module.runtime_service, "generate", lambda req: _stub_response(invalid_binding_json))

    result = task_decomposer.maybe_decompose(
        context=SupervisorContext(owner_id="42", question="Check the database and search Drive for this."),
        intent=INTENT,
    )

    assert result is None
