"""
WritingAgent (Phase 23): outbound draft composition.

Tools: none -- text only, no side effects. Wraps app.core.ai's ai_service
exactly as the four passthrough methods this file used to expose did; this
replaces those methods with the Agent contract's single `run()` entry point
(PHASE_23.md Task 6). Sending a drafted email is a separate, explicit,
approval-gated capability (gmail.send / GmailSendHandler) that no agent may
hold -- this agent's output carries `send_capability` to say so, never
performs it.
"""
from typing import Literal, Optional

from pydantic import BaseModel

from app.agents.base import Agent, AgentContext, AgentResult, AgentSpec
from app.core.ai import ai_service


class WritingRequest(BaseModel):
    kind: Literal["email", "rewrite", "reply", "generate"] = "generate"
    instruction: Optional[str] = ""
    text: Optional[str] = ""
    email: Optional[str] = ""


class Draft(BaseModel):
    subject: str = ""
    body: str = ""
    send_capability: Optional[str] = "gmail.send"


class WritingAgent(Agent):
    spec = AgentSpec(
        name="WritingAgent",
        role="outbound draft composition",
        input_schema=WritingRequest,
        output_schema=Draft,
        tools=["ai_service"],
        reads_state=[],
        writes_state=[],
        side_effect="read_only",
        requires_human_approval=False,
    )

    def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
        assert isinstance(inputs, WritingRequest)

        if inputs.kind == "email":
            body = ai_service.write_email(inputs.instruction or "Write a professional email")
            draft = Draft(subject="", body=body)
        elif inputs.kind == "rewrite":
            body = ai_service.rewrite(inputs.text or "", inputs.instruction or "Improve tone and clarity")
            draft = Draft(subject="", body=body)
        elif inputs.kind == "reply":
            body = ai_service.professional_reply(inputs.email or "", inputs.instruction or "Draft professional response")
            draft = Draft(subject="", body=body)
        else:
            body = ai_service.generate(inputs.instruction or inputs.text or "Generate content", provider="openrouter")
            draft = Draft(subject="", body=body)

        return AgentResult(output=draft, evidence=[], notes=f"kind={inputs.kind}")


writing_agent = WritingAgent()
