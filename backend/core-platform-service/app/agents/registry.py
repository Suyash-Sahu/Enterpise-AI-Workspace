"""
Agent registry (Phase 23), mirroring app/execution/registry.py's TaskRegistry
shape -- register-by-name, get-by-name, list -- but for the new Agent
contract instead of ExecutionHandler.

Two assertions are enforced here, for real, not just documented:
1. An agent with no AgentSpec is a registration-time error.
2. An agent declaring a side_effect other than "read_only" is a
   registration-time error -- side effects stay reachable only through
   ExecutionHandler + the executor's approval gate (PHASE_23.md's core
   security invariant: no agent may hold a side-effecting tool).
"""
import logging
from typing import Dict

from app.agents.base import Agent, AgentSpec

logger = logging.getLogger(__name__)


class AgentRegistry:

    def __init__(self):
        self._agents: Dict[str, Agent] = {}

    def register(self, agent: Agent):
        spec = getattr(agent, "spec", None)
        if not isinstance(spec, AgentSpec):
            raise ValueError(
                f"Agent {type(agent).__name__} has no AgentSpec -- every Agent "
                "must declare one (see app/agents/base.py)."
            )
        if spec.side_effect != "read_only":
            raise ValueError(
                f"Agent '{spec.name}' ({type(agent).__name__}) declares "
                f"side_effect={spec.side_effect!r}. No agent may hold a "
                "side-effecting tool -- side effects are only reachable "
                "through ExecutionHandler + the executor's approval gate."
            )
        self._agents[spec.name] = agent
        logger.info(f"Registered agent: '{spec.name}'")

    def get_agent(self, name: str) -> Agent:
        if name not in self._agents:
            raise ValueError(f"Unknown agent '{name}'. Registered agents: {list(self._agents.keys())}")
        return self._agents[name]

    def list_agents(self) -> list[str]:
        return list(self._agents.keys())

    def list_specs(self) -> list[AgentSpec]:
        return [self._agents[name].spec for name in sorted(self._agents)]


agent_registry = AgentRegistry()


def _register_default_agents():
    # Imported lazily, inside the function, so importing app.agents.registry
    # (e.g. from a test that only wants AgentRegistry itself) never forces a
    # chain-import of every specialized agent module and the services they wrap.
    from app.agents.inbox_agent import inbox_triage_agent
    from app.agents.calendar_agent import calendar_agent
    from app.agents.knowledge_agent import knowledge_agent
    from app.agents.database_agent import data_agent
    from app.agents.task_agent import task_agent
    from app.agents.meeting_agent import meeting_extraction_agent
    from app.agents.reconciler_agent import reconciler_agent
    from app.agents.writing_agent import writing_agent
    from app.agents.document_agent import document_ops_agent

    for agent in (
        inbox_triage_agent,
        calendar_agent,
        knowledge_agent,
        data_agent,
        task_agent,
        meeting_extraction_agent,
        reconciler_agent,
        writing_agent,
        document_ops_agent,
    ):
        agent_registry.register(agent)


_register_default_agents()
