"""
Phase 23: the Agent contract's two registration-time invariants, enforced in
app/agents/registry.py's AgentRegistry.register() -- not just documented.

1. An agent with no AgentSpec is a registration-time error (mirrors
   app/execution/registry.py's TaskRegistry rejecting a handler with no
   CapabilityMetadata).
2. An agent declaring a side_effect other than "read_only" is a
   registration-time error -- no agent may hold a side-effecting tool; side
   effects stay reachable only through ExecutionHandler + the executor's
   approval gate.
"""
import pytest
from pydantic import BaseModel

from app.agents.base import Agent, AgentContext, AgentResult, AgentSpec
from app.agents.registry import AgentRegistry


class _DummyInput(BaseModel):
    pass


class _DummyOutput(BaseModel):
    pass


def test_register_rejects_agent_without_spec():
    class NoSpecAgent(Agent):
        def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
            return AgentResult(output=_DummyOutput())

    registry = AgentRegistry()
    with pytest.raises(ValueError, match="AgentSpec"):
        registry.register(NoSpecAgent())


def test_register_rejects_agent_with_non_read_only_side_effect():
    class SideEffectingAgent(Agent):
        spec = AgentSpec(
            name="SideEffectingAgent",
            role="a rogue agent trying to hold a write",
            input_schema=_DummyInput,
            output_schema=_DummyOutput,
            tools=["GmailSendHandler"],
            side_effect="external_communication",
        )

        def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
            return AgentResult(output=_DummyOutput())

    registry = AgentRegistry()
    with pytest.raises(ValueError, match="side-effecting tool"):
        registry.register(SideEffectingAgent())


def test_register_accepts_a_well_formed_read_only_agent():
    class FineAgent(Agent):
        spec = AgentSpec(
            name="FineAgent",
            role="does nothing side-effecting",
            input_schema=_DummyInput,
            output_schema=_DummyOutput,
            tools=[],
            side_effect="read_only",
        )

        def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
            return AgentResult(output=_DummyOutput())

    registry = AgentRegistry()
    registry.register(FineAgent())
    assert "FineAgent" in registry.list_agents()
    assert registry.get_agent("FineAgent").spec.side_effect == "read_only"


def test_default_agent_registry_has_all_nine_specialized_agents_and_none_side_effecting():
    """
    PHASE_23.md names 8 specialized agents in Task 3 but its Definition of
    Done says "all nine agents registered" and lists document_agent.py among
    the files to modify -- resolved by adding DocumentAgent as the 9th
    (role: document operations, wrapping DocumentService). See
    docs/research/PHASE_PROGRESS_11_22.md's Phase 23 section for the full
    resolution.
    """
    from app.agents.registry import agent_registry

    expected = {
        "InboxAgent", "CalendarAgent", "KnowledgeAgent", "DataAgent",
        "TaskAgent", "MeetingAgent", "ReconcilerAgent", "WritingAgent",
        "DocumentAgent",
    }
    assert set(agent_registry.list_agents()) == expected
    for spec in agent_registry.list_specs():
        assert spec.side_effect == "read_only", f"{spec.name} is not read_only"
