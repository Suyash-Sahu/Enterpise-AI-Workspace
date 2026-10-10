"""
Phase 26 tests: DagScheduler (topological readiness, deadlock detection, failure propagation).
Pure tests over PlanStep state without database or model calls.
"""
import pytest
from app.schemas.supervisor import PlanStep, SupervisorPlan
from app.supervisor.scheduler import DagScheduler, dag_scheduler
from app.runtime.exceptions import RuntimePolicyError


def test_ready_steps_initial_state():
    """Independent steps (depends_on=[]) are immediately ready."""
    s1 = PlanStep(step_id="step_1", capability="rag_search", depends_on=[])
    s2 = PlanStep(step_id="step_2", capability="database_query", depends_on=[])
    s3 = PlanStep(step_id="step_3", capability="text_generation", depends_on=["step_1", "step_2"])

    ready = dag_scheduler.ready_steps([s1, s2, s3])
    ready_ids = [s.step_id for s in ready]
    assert sorted(ready_ids) == ["step_1", "step_2"]


def test_diamond_dependency_topological_execution():
    """
    Diamond graph:
        A
       / \
      B   C
       \ /
        D
    Executes in topological order: A -> {B, C} -> D.
    """
    sA = PlanStep(step_id="A", capability="rag_search", depends_on=[])
    sB = PlanStep(step_id="B", capability="database_query", depends_on=["A"])
    sC = PlanStep(step_id="C", capability="document_summary", depends_on=["A"])
    sD = PlanStep(step_id="D", capability="text_generation", depends_on=["B", "C"])

    plan_steps = [sA, sB, sC, sD]

    # Iteration 1: Only A is ready
    ready = dag_scheduler.ready_steps(plan_steps)
    assert [s.step_id for s in ready] == ["A"]

    # Mark A COMPLETED
    sA.status = "COMPLETED"

    # Iteration 2: B and C are ready
    ready = dag_scheduler.ready_steps(plan_steps)
    assert sorted([s.step_id for s in ready]) == ["B", "C"]

    # Mark B COMPLETED (C still PENDING)
    sB.status = "COMPLETED"
    ready = dag_scheduler.ready_steps(plan_steps)
    assert [s.step_id for s in ready] == ["C"]  # D not ready until C finishes

    # Mark C COMPLETED
    sC.status = "COMPLETED"
    ready = dag_scheduler.ready_steps(plan_steps)
    assert [s.step_id for s in ready] == ["D"]

    # Mark D COMPLETED
    sD.status = "COMPLETED"
    ready = dag_scheduler.ready_steps(plan_steps)
    assert ready == []


def test_deadlock_detection_raises_policy_error():
    """Unresolvable dependency loop / deadlock raises RuntimePolicyError."""
    # A depends on B, B depends on A (both PENDING)
    sA = PlanStep(step_id="A", capability="rag_search", depends_on=["B"])
    sB = PlanStep(step_id="B", capability="database_query", depends_on=["A"])

    steps = [sA, sB]
    ready = dag_scheduler.ready_steps(steps)
    assert ready == []

    with pytest.raises(RuntimePolicyError) as exc_info:
        dag_scheduler.detect_deadlock(steps)

    assert "Deadlock detected" in str(exc_info.value)


def test_transitive_dependents_and_failure_propagation():
    """
    A -> C -> D
    B (independent)

    Failing A must mark C and D BLOCKED with blocked_by_step_id="A".
    B remains PENDING.
    """
    sA = PlanStep(step_id="A", capability="rag_search", depends_on=[])
    sB = PlanStep(step_id="B", capability="database_query", depends_on=[])
    sC = PlanStep(step_id="C", capability="document_summary", depends_on=["A"])
    sD = PlanStep(step_id="D", capability="text_generation", depends_on=["C"])

    steps = [sA, sB, sC, sD]
    sA.status = "FAILED"

    blocked = dag_scheduler.mark_blocked(steps, "A")
    assert sorted(blocked) == ["C", "D"]

    assert sC.status == "BLOCKED"
    assert sC.blocked_by_step_id == "A"

    assert sD.status == "BLOCKED"
    assert sD.blocked_by_step_id == "A"

    assert sB.status == "PENDING"
