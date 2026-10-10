"""
TaskAgent (Phase 23): work-state read and proposal.

Tools: WorkGraphService (workgraph_service). Proposes tasks; does not write
in this phase -- task creation stays the separate, explicit
workgraph.create_task capability (CreateTaskHandler), which no agent may
hold per the standing side-effect invariant.
"""
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.base import Agent, AgentContext, AgentResult, AgentSpec
from app.services.workgraph_service import workgraph_service


class TaskViewInput(BaseModel):
    project_id: Optional[str] = None
    status: Optional[str] = None
    assignee: Optional[str] = None


class TaskView(BaseModel):
    tasks: list[dict] = Field(default_factory=list)
    overdue: list[dict] = Field(default_factory=list)
    proposed_tasks: list[dict] = Field(default_factory=list)


def _task_dict(t) -> dict:
    return {
        "id": t.id,
        "title": t.title,
        "status": t.status,
        "priority": t.priority,
        "due_date": t.due_date.isoformat() if t.due_date else None,
    }


class TaskAgent(Agent):
    spec = AgentSpec(
        name="TaskAgent",
        role="work-state read and proposal",
        input_schema=TaskViewInput,
        output_schema=TaskView,
        tools=["workgraph_service"],
        reads_state=["owner_id"],
        writes_state=[],
        side_effect="read_only",
        requires_human_approval=False,
    )

    def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
        assert isinstance(inputs, TaskViewInput)
        tasks = workgraph_service.list_tasks(
            db=ctx.db, owner_id=ctx.owner_id,
            project_id=inputs.project_id, status=inputs.status, assignee=inputs.assignee,
        )
        now = datetime.now(timezone.utc)
        overdue = [
            t for t in tasks
            if t.due_date is not None
            and t.status != "done"
            and (t.due_date if t.due_date.tzinfo else t.due_date.replace(tzinfo=timezone.utc)) < now
        ]
        view = TaskView(
            tasks=[_task_dict(t) for t in tasks],
            overdue=[_task_dict(t) for t in overdue],
            # This agent only proposes -- it never calls
            # workgraph_service.create_task, so proposed_tasks stays empty
            # until a caller (e.g. a future replanning phase) adds real
            # proposal logic on top of this read.
            proposed_tasks=[],
        )
        return AgentResult(output=view, evidence=[str(t.id) for t in tasks])


task_agent = TaskAgent()
