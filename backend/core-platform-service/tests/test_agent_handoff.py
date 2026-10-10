"""
Phase 25: typed agent-to-agent result passing.

Covers:
- a valid input_binding resolves at both plan-validation time
  (validate_dag_plan) and runtime (resolve_step_input);
- a binding naming a nonexistent producer field is rejected at plan
  validation with a message naming the field;
- a type-incompatible edge (no adapter, no direct type match) is rejected
  before execution;
- producer/consumer capabilities absent from CAPABILITY_AGENT_MAP (no
  declared Agent schema) are rejected rather than silently allowed through;
- the Task 3 example adapter (InboxFindings.extracted_commitments ->
  ReconcilerAgent's ReconcileInput.items) is a real, hand-written
  conversion, not inferred coercion.
"""
import pytest

from app.agents.handoff import (
    PathResolutionError,
    get_adapter,
    parse_binding_ref,
    resolve_declared_type,
    resolve_runtime_value,
    types_compatible,
)
from app.agents.reconciler_agent import ReconcileItem
from app.runtime.exceptions import RuntimePolicyError
from app.schemas.supervisor import PlanStep
from app.supervisor.context import SupervisorContext
from app.supervisor.planner import supervisor_planner
from app.supervisor.policies import supervisor_policy


# --- parse_binding_ref -------------------------------------------------

def test_parse_binding_ref_extracts_step_id_and_path():
    dep_id, path = parse_binding_ref("$step.step_1.output.sql")
    assert dep_id == "step_1"
    assert path == "sql"


def test_parse_binding_ref_supports_nested_path():
    dep_id, path = parse_binding_ref("$step.step_1.output.foo.bar")
    assert dep_id == "step_1"
    assert path == "foo.bar"


@pytest.mark.parametrize("bad_ref", ["$step.step_1.result", "not_a_ref", "$context.question", "$step..output.x"])
def test_parse_binding_ref_rejects_malformed_or_untyped_refs(bad_ref):
    with pytest.raises(PathResolutionError):
        parse_binding_ref(bad_ref)


# --- resolve_declared_type ----------------------------------------------

def test_resolve_declared_type_finds_a_real_field():
    from app.agents.database_agent import RowSet
    assert resolve_declared_type(RowSet, "sql") is str


def test_resolve_declared_type_rejects_nonexistent_field():
    from app.agents.database_agent import RowSet
    with pytest.raises(PathResolutionError) as exc_info:
        resolve_declared_type(RowSet, "nonexistent_field")
    assert "nonexistent_field" in str(exc_info.value)


def test_resolve_runtime_value_walks_a_dict():
    assert resolve_runtime_value({"sql": "SELECT 1", "rows": []}, "sql") == "SELECT 1"


def test_resolve_runtime_value_returns_none_for_missing_key():
    assert resolve_runtime_value({"sql": "SELECT 1"}, "missing") is None


# --- Task 3 adapter registry ---------------------------------------------

def test_extracted_commitments_adapter_is_registered_and_hand_written():
    from app.agents.inbox_agent import InboxFindings

    producer_type = resolve_declared_type(InboxFindings, "extracted_commitments")
    adapter = get_adapter(producer_type, list[ReconcileItem])
    assert adapter is not None

    result = adapter([{"key": "budget", "value": "10k", "source": "email_1"}])
    assert len(result) == 1
    assert isinstance(result[0], ReconcileItem)
    assert result[0].key == "budget"
    assert result[0].value == "10k"
    assert result[0].source == "email_1"


def test_types_compatible_direct_match_needs_no_adapter():
    assert types_compatible(str, str) is True
    assert types_compatible(list, list) is True
    assert types_compatible(dict, str) is False


# --- validate_dag_plan: typed edge validation ----------------------------

def test_valid_input_binding_passes_plan_validation():
    step1 = PlanStep(step_id="step_1", capability="database_query", depends_on=[])
    step2 = PlanStep(
        step_id="step_2",
        capability="database_query",
        depends_on=["step_1"],
        input_bindings={"question": "$step.step_1.output.sql"},
    )
    # Must not raise.
    supervisor_policy.validate_dag_plan([step1, step2])


def test_binding_naming_nonexistent_producer_field_is_rejected():
    step1 = PlanStep(step_id="step_1", capability="database_query", depends_on=[])
    step2 = PlanStep(
        step_id="step_2",
        capability="database_query",
        depends_on=["step_1"],
        input_bindings={"question": "$step.step_1.output.not_a_real_field"},
    )
    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1, step2])
    assert "not_a_real_field" in str(exc_info.value)


def test_type_incompatible_binding_is_rejected_before_execution():
    step1 = PlanStep(step_id="step_1", capability="database_query", depends_on=[])
    step2 = PlanStep(
        step_id="step_2",
        capability="database_query",
        depends_on=["step_1"],
        # RowSet.rows is list[dict]; DataAgentInput.limit is int. No direct
        # match, no adapter registered for (list[dict], int).
        input_bindings={"limit": "$step.step_1.output.rows"},
    )
    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1, step2])
    assert "limit" in str(exc_info.value)


def test_binding_against_a_capability_with_no_typed_output_is_rejected():
    """text_generation has no entry in CAPABILITY_AGENT_MAP (its handler
    calls runtime_service directly, not a registered Agent) -- a binding
    naming it as a producer must be a plan-validation rejection, not a
    silently-allowed pass-through."""
    step1 = PlanStep(step_id="step_1", capability="text_generation", depends_on=[])
    step2 = PlanStep(
        step_id="step_2",
        capability="database_query",
        depends_on=["step_1"],
        input_bindings={"question": "$step.step_1.output.generated_text"},
    )
    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1, step2])
    assert "no typed output" in str(exc_info.value)


def test_binding_into_a_capability_with_no_typed_input_is_rejected():
    """gmail.send has no entry in CAPABILITY_AGENT_MAP either -- a binding
    into it as a consumer must also be rejected."""
    step1 = PlanStep(step_id="step_1", capability="database_query", depends_on=[])
    step2 = PlanStep(
        step_id="step_2",
        capability="gmail.send",
        depends_on=["step_1"],
        input_bindings={"body": "$step.step_1.output.sql"},
    )
    with pytest.raises(RuntimePolicyError) as exc_info:
        supervisor_policy.validate_dag_plan([step1, step2])
    assert "no typed input schema" in str(exc_info.value)


def test_binding_referencing_a_step_that_runs_later_is_rejected():
    """Plan steps execute sequentially in list order (see
    AMOFSupervisor.run); a binding referencing a step that hasn't run yet by
    that point is as invalid as referencing an unknown step."""
    step1 = PlanStep(
        step_id="step_1",
        capability="database_query",
        depends_on=[],
        input_bindings={"question": "$step.step_2.output.sql"},
    )
    step2 = PlanStep(step_id="step_2", capability="database_query", depends_on=[])
    with pytest.raises(RuntimePolicyError):
        supervisor_policy.validate_dag_plan([step1, step2])


# --- resolve_step_input: runtime resolution ------------------------------

def test_resolve_step_input_resolves_a_valid_typed_binding_at_runtime():
    step1 = PlanStep(
        step_id="step_1",
        capability="database_query",
        depends_on=[],
        status="COMPLETED",
        result={"result": {"rows": [], "sql": "SELECT 1", "owner_predicate_verified": True}},
    )
    step2 = PlanStep(
        step_id="step_2",
        capability="database_query",
        depends_on=["step_1"],
        input_bindings={"question": "$step.step_1.output.sql"},
    )
    context = SupervisorContext(owner_id="1", question="irrelevant")

    resolved = supervisor_planner.resolve_step_input(
        step=step2, context=context, completed_steps={"step_1": step1},
    )
    assert resolved["question"] == "SELECT 1"


def test_resolve_step_input_typed_binding_fails_closed_to_none_when_producer_incomplete():
    step2 = PlanStep(
        step_id="step_2",
        capability="database_query",
        depends_on=["step_1"],
        input_bindings={"question": "$step.step_1.output.sql"},
    )
    context = SupervisorContext(owner_id="1", question="irrelevant")

    resolved = supervisor_planner.resolve_step_input(
        step=step2, context=context, completed_steps={},
    )
    assert resolved["question"] is None
