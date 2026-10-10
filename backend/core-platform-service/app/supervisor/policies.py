import logging
from app.core.config import settings
from app.schemas.supervisor import IntentResult, PlanStep
from app.runtime.exceptions import RuntimePolicyError
from app.execution.registry import task_registry
from app.agents.registry import agent_registry
from app.agents.handoff import (
    CAPABILITY_AGENT_MAP,
    PathResolutionError,
    get_adapter,
    parse_binding_ref,
    resolve_declared_type,
    types_compatible,
    unwrap_optional,
)

logger = logging.getLogger(__name__)

# Previously a hand-maintained set duplicating TaskRegistry's own 5
# registered capabilities -- a second source of truth with no automated
# link to the first, exactly the kind of drift this project has already hit
# more than once (config settings pointing at two different model names,
# etc.). task_registry is the actual registration point (see
# app/execution/registry.py); this reads from it live instead of hoping a
# human updates both places whenever a capability is added or removed.


def _allowed_capabilities() -> set[str]:
    return set(task_registry.list_supported_tasks())


class SupervisorPolicy:

    @staticmethod
    def validate_intent(intent: IntentResult) -> bool:
        """
        Validates intent capability against the live registry and checks
        confidence threshold (0.70).
        """
        allowed = _allowed_capabilities()
        if intent.capability not in allowed:
            raise RuntimePolicyError(f"Unauthorized capability '{intent.capability}'. Allowed capabilities: {sorted(allowed)}")

        return intent.confidence >= settings.SUPERVISOR_INTENT_CONFIDENCE_THRESHOLD

    @staticmethod
    def validate_timeout(requested_timeout: float | None) -> float:
        """
        Caps requested supervisor timeout at SUPERVISOR_MAX_TIMEOUT (120.0s).
        """
        t_out = requested_timeout if requested_timeout is not None else settings.SUPERVISOR_DEFAULT_TIMEOUT
        return min(max(1.0, t_out), settings.SUPERVISOR_MAX_TIMEOUT)

    @staticmethod
    def validate_dag_plan(steps: list[PlanStep]):
        """
        Validates DAG plan structure:
        1. Max steps limit (<= 5)
        2. Unique step IDs
        3. Every step references a real, registered capability (AMOF-X
           Phase 2: a decomposer -- LLM-driven or otherwise -- must not be
           able to invent a capability that doesn't exist)
        4. Valid prerequisite dependency references
        5. Cycle detection (Kahn's / DFS algorithm)
        """
        if len(steps) > settings.SUPERVISOR_MAX_STEPS:
            raise RuntimePolicyError(f"Plan exceeds maximum allowed steps ({len(steps)} > {settings.SUPERVISOR_MAX_STEPS}).")

        allowed_capabilities = _allowed_capabilities()
        step_ids = set()
        for step in steps:
            if step.step_id in step_ids:
                raise RuntimePolicyError(f"Duplicate step ID '{step.step_id}' found in plan.")
            step_ids.add(step.step_id)
            if step.capability not in allowed_capabilities:
                raise RuntimePolicyError(
                    f"Step '{step.step_id}' references unregistered capability "
                    f"'{step.capability}'. Registered: {sorted(allowed_capabilities)}"
                )

        # Build adjacency graph for cycle detection
        adj = {step.step_id: [] for step in steps}
        for step in steps:
            for dep in step.depends_on:
                if dep not in step_ids:
                    raise RuntimePolicyError(f"Step '{step.step_id}' references unknown dependency '{dep}'.")
                adj[dep].append(step.step_id)

        # DFS Cycle Detection
        visited = {}  # 0 = unvisited, 1 = visiting, 2 = visited

        def dfs(node: str):
            visited[node] = 1
            for neighbor in adj.get(node, []):
                if visited.get(neighbor, 0) == 1:
                    raise RuntimePolicyError(f"Cyclic dependency detected in execution graph involving step '{neighbor}'.")
                if visited.get(neighbor, 0) == 0:
                    dfs(neighbor)
            visited[node] = 2

        for step in steps:
            if visited.get(step.step_id, 0) == 0:
                dfs(step.step_id)

        # Phase 25: type-check every edge implied by input_bindings
        SupervisorPolicy._validate_input_bindings(steps, step_ids)

        # Phase 27: reject concurrently-ready steps writing to the same state key
        SupervisorPolicy._validate_parallel_state_conflicts(steps)

    @staticmethod
    def _validate_parallel_state_conflicts(steps: list[PlanStep]) -> None:
        """
        Phase 27: Reject at plan validation any two mutually independent steps
        that declare write access to the same state key (writes_state).
        """
        from app.supervisor.scheduler import DagScheduler

        writes_map: dict[str, set[str]] = {}
        for step in steps:
            agent_name = CAPABILITY_AGENT_MAP.get(step.capability)
            if agent_name:
                try:
                    spec = agent_registry.get_agent(agent_name).spec
                    if spec.writes_state:
                        writes_map[step.step_id] = set(spec.writes_state)
                except ValueError:
                    pass

        step_ids_with_writes = list(writes_map.keys())
        for i in range(len(step_ids_with_writes)):
            id1 = step_ids_with_writes[i]
            deps1 = DagScheduler.get_transitive_dependents(steps, id1)
            for j in range(i + 1, len(step_ids_with_writes)):
                id2 = step_ids_with_writes[j]
                deps2 = DagScheduler.get_transitive_dependents(steps, id2)

                is_dependent = (id2 in deps1) or (id1 in deps2)
                if not is_dependent:
                    common_keys = writes_map[id1].intersection(writes_map[id2])
                    if common_keys:
                        key_name = sorted(common_keys)[0]
                        raise RuntimePolicyError(
                            f"Plan validation rejected: mutually independent steps '{id1}' and '{id2}' "
                            f"both declare write access to state key '{key_name}'."
                        )

    @staticmethod
    def _validate_input_bindings(steps: list[PlanStep], step_ids: set[str]) -> None:
        step_index = {step.step_id: i for i, step in enumerate(steps)}

        for step in steps:
            for field_name, ref in step.input_bindings.items():
                try:
                    dep_id, path = parse_binding_ref(ref)
                except PathResolutionError as exc:
                    raise RuntimePolicyError(
                        f"Step '{step.step_id}' input_binding '{field_name}': {exc}"
                    ) from exc

                if dep_id not in step_ids:
                    raise RuntimePolicyError(
                        f"Step '{step.step_id}' input_binding '{field_name}' references "
                        f"unknown producer step '{dep_id}'."
                    )
                from app.supervisor.scheduler import DagScheduler
                transitive_deps = DagScheduler.get_transitive_dependents(steps, dep_id)
                if step.step_id not in transitive_deps and step_index[dep_id] >= step_index[step.step_id]:
                    raise RuntimePolicyError(
                        f"Step '{step.step_id}' input_binding '{field_name}' references "
                        f"producer step '{dep_id}', which does not run before it "
                        "(producer must be a prerequisite in the execution DAG)."
                    )

                producer_step = steps[step_index[dep_id]]
                producer_agent_name = CAPABILITY_AGENT_MAP.get(producer_step.capability)
                if not producer_agent_name:
                    raise RuntimePolicyError(
                        f"Step '{step.step_id}' input_binding '{field_name}': producer "
                        f"capability '{producer_step.capability}' (step '{dep_id}') has no "
                        "typed output available for binding."
                    )
                producer_spec = agent_registry.get_agent(producer_agent_name).spec

                try:
                    producer_type = resolve_declared_type(producer_spec.output_schema, path)
                except PathResolutionError as exc:
                    raise RuntimePolicyError(
                        f"Step '{step.step_id}' input_binding '{field_name}' -> '{ref}': {exc}"
                    ) from exc

                consumer_agent_name = CAPABILITY_AGENT_MAP.get(step.capability)
                if not consumer_agent_name:
                    raise RuntimePolicyError(
                        f"Step '{step.step_id}' input_binding '{field_name}': consumer "
                        f"capability '{step.capability}' has no typed input schema available "
                        "for binding."
                    )
                consumer_spec = agent_registry.get_agent(consumer_agent_name).spec
                consumer_field = consumer_spec.input_schema.model_fields.get(field_name)
                if consumer_field is None:
                    raise RuntimePolicyError(
                        f"Step '{step.step_id}' input_binding: field '{field_name}' does not "
                        f"exist on {consumer_spec.input_schema.__name__} "
                        f"(declared fields: {sorted(consumer_spec.input_schema.model_fields)})."
                    )
                consumer_type = unwrap_optional(consumer_field.annotation)

                if types_compatible(producer_type, consumer_type):
                    continue
                if get_adapter(producer_type, consumer_type) is not None:
                    continue

                raise RuntimePolicyError(
                    f"Step '{step.step_id}' input_binding '{field_name}': producer type "
                    f"{producer_type!r} (from '{ref}') is not compatible with consumer field "
                    f"'{field_name}' type {consumer_type!r}, and no adapter is registered."
                )


supervisor_policy = SupervisorPolicy()
