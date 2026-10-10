"""
Phase 23: the Agent contract.

Before this, `app/agents/*` were not agents -- `writing_agent.py` was four
passthrough methods to `ai_service`, and every other "agent" was one
stateless LLM call with no declared interface. Nothing distinguished an
agent from a plain function call, so there was no unit to register, verify,
or attribute failure to.

`AgentSpec` mirrors `app.execution.contracts.CapabilityMetadata`'s
enforce-at-registration discipline: an agent with no spec is a
registration-time error (enforced in `app/agents/registry.py`), not a
silent default.

The standing security invariant this phase adds in code, not prose: no
agent may hold a side-effecting tool. Side effects (gmail.send,
workgraph.create_task) stay reachable only through `ExecutionHandler` +
the executor's approval gate -- `AgentRegistry.register()` rejects any
agent that declares a `side_effect` other than `"read_only"`.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session


@dataclass
class AgentContext:
    """
    Parallels app.execution.contracts.ExecutionContext, plus the DB session
    every agent needs to read state through -- ExecutionContext doesn't carry
    one because handlers receive `db` as a separate execute() argument, but
    an agent's single `run(ctx, inputs)` signature has nowhere else to put it.
    """
    owner_id: str
    db: Optional[Session] = None
    execution_mode: str = "auto"
    timeout: float = 60.0
    request_id: Optional[str] = None
    execution_id: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentSpec:
    """
    What an agent IS, declared by the agent itself rather than inferred at
    call time. `side_effect` reuses CapabilityMetadata's vocabulary
    ("read_only" | "reversible_write" | "irreversible_write" |
    "external_communication" | "destructive") but every agent must declare
    "read_only" -- see the module docstring's security invariant.
    """
    name: str
    role: str
    input_schema: type[BaseModel]
    output_schema: type[BaseModel]
    tools: list[str]
    reads_state: list[str] = field(default_factory=list)
    writes_state: list[str] = field(default_factory=list)
    side_effect: str = "read_only"
    requires_human_approval: bool = False
    # Phase 29: optional reference to the step verifier type that applies to
    # this agent's output. Informational -- per-step verification routes by
    # capability through app/supervisor/verifiers/dispatcher.py, not by this
    # field -- but declared on the spec so the producer declares its own
    # verification contract rather than it being inferred at call time.
    verifier: Optional[str] = None


class AgentResult(BaseModel):
    """
    What every agent hands back, regardless of domain: an output plus enough
    metadata (evidence, confidence, cost accounting) to schedule, verify and
    attribute failure to later -- exactly the thing a bare function call
    can't carry.
    """
    output: Any
    evidence: list[str] = []
    confidence: Optional[float] = None
    cost: Optional[float] = None
    latency_ms: Optional[float] = None
    model: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"arbitrary_types_allowed": True}


class Agent(ABC):
    """
    One method, deliberately: an agent is a unit that turns declared inputs
    into a declared, attributable output. Every concrete agent must set
    `spec` as a class attribute (parallels ExecutionHandler.metadata) -- no
    default, so an agent that forgets it fails at registration time rather
    than silently running unregistered.
    """
    spec: AgentSpec

    @abstractmethod
    def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
        ...
