"""
AMOF-X Phase 26: Real DAG Dependency Execution.

`DagScheduler` provides pure-function topological scheduling, deadlock detection,
and descendant-only failure propagation over `PlanStep` graphs.
"""
from typing import Union
from app.schemas.supervisor import SupervisorPlan, PlanStep
from app.runtime.exceptions import RuntimePolicyError


class DagScheduler:

    @staticmethod
    def _extract_steps(plan_or_steps: Union[SupervisorPlan, list[PlanStep]]) -> list[PlanStep]:
        if isinstance(plan_or_steps, SupervisorPlan):
            return plan_or_steps.steps
        return plan_or_steps

    @staticmethod
    def ready_steps(
        plan_or_steps: Union[SupervisorPlan, list[PlanStep]],
        completed_ids: set[str] | None = None,
    ) -> list[PlanStep]:
        """
        Returns steps whose status is PENDING and whose dependencies (depends_on)
        are all COMPLETED (or present in completed_ids if provided).
        """
        steps = DagScheduler._extract_steps(plan_or_steps)
        if completed_ids is None:
            completed_ids = {s.step_id for s in steps if s.status == "COMPLETED"}

        ready = []
        for step in steps:
            if step.status != "PENDING":
                continue
            if all(dep in completed_ids for dep in step.depends_on):
                ready.append(step)
        return ready

    @staticmethod
    def get_transitive_dependents(
        plan_or_steps: Union[SupervisorPlan, list[PlanStep]],
        failed_step_id: str,
    ) -> set[str]:
        """
        Computes all step IDs that transitively depend on failed_step_id.
        """
        steps = DagScheduler._extract_steps(plan_or_steps)
        # Build adjacency: node -> list of steps that depend on node
        dependents_map: dict[str, list[str]] = {s.step_id: [] for s in steps}
        for s in steps:
            for dep in s.depends_on:
                if dep in dependents_map:
                    dependents_map[dep].append(s.step_id)

        visited: set[str] = set()
        queue = [failed_step_id]
        while queue:
            curr = queue.pop(0)
            for child in dependents_map.get(curr, []):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)
        return visited

    @staticmethod
    def mark_blocked(
        plan_or_steps: Union[SupervisorPlan, list[PlanStep]],
        failed_step_id: str,
    ) -> list[str]:
        """
        Marks all transitive dependents of failed_step_id as BLOCKED
        (recording blocked_by_step_id), provided their status is currently PENDING.
        Returns the list of step IDs that were marked BLOCKED.
        """
        steps = DagScheduler._extract_steps(plan_or_steps)
        step_map = {s.step_id: s for s in steps}
        transitive_deps = DagScheduler.get_transitive_dependents(steps, failed_step_id)

        newly_blocked = []
        for dep_id in transitive_deps:
            s = step_map.get(dep_id)
            if s and s.status == "PENDING":
                s.status = "BLOCKED"
                s.blocked_by_step_id = failed_step_id
                newly_blocked.append(dep_id)
        return newly_blocked

    @staticmethod
    def detect_deadlock(plan_or_steps: Union[SupervisorPlan, list[PlanStep]]) -> None:
        """
        Raises RuntimePolicyError if unfinished (PENDING) steps remain,
        none are ready, and none are RUNNING.
        """
        steps = DagScheduler._extract_steps(plan_or_steps)
        pending_steps = [s for s in steps if s.status == "PENDING"]
        if not pending_steps:
            return

        running_steps = [s for s in steps if s.status == "RUNNING"]
        ready = DagScheduler.ready_steps(steps)
        if not ready and not running_steps:
            pending_ids = [s.step_id for s in pending_steps]
            raise RuntimePolicyError(
                f"Deadlock detected in DAG execution: steps {pending_ids} cannot be satisfied."
            )


dag_scheduler = DagScheduler()
