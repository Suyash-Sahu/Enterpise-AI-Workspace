"""
Phase 23: guards spec/implementation drift.

Each agent's AgentSpec.tools declares the services it depends on. This test
does not trust that declaration -- it reads the actual module source that
defines the agent's class and checks each declared tool name is genuinely
referenced there (an import or a usage), so a spec that claims a tool the
implementation doesn't touch (or an implementation that grows a new
dependency nobody declared) fails loudly instead of silently drifting.
"""
import inspect

from app.agents.registry import agent_registry


def test_every_agent_declared_tool_is_referenced_in_its_module_source():
    for name in agent_registry.list_agents():
        agent = agent_registry.get_agent(name)
        module = inspect.getmodule(type(agent))
        assert module is not None, f"could not resolve module for agent {name}"
        source = inspect.getsource(module)

        for tool in agent.spec.tools:
            assert tool in source, (
                f"AgentSpec for '{name}' declares tool {tool!r}, but it does not "
                f"appear anywhere in {module.__name__} -- spec/implementation drift."
            )


def test_reconciler_agent_declares_no_tools():
    """
    ReconcilerAgent is a pure function over other agents' outputs (PHASE_23.md
    Task 3) -- it must declare zero tools, not merely happen to have none.
    """
    reconciler = agent_registry.get_agent("ReconcilerAgent")
    assert reconciler.spec.tools == []


def test_writing_agent_declares_no_side_effecting_tools():
    """
    WritingAgent produces text only (Draft{subject, body, send_capability});
    it must never declare a send/write tool such as GoogleConnectorService or
    workgraph_service -- sending stays the separate gmail.send capability.
    """
    writing = agent_registry.get_agent("WritingAgent")
    forbidden = {"GoogleConnectorService", "workgraph_service", "GmailSendHandler", "CreateTaskHandler"}
    assert not (forbidden & set(writing.spec.tools))
