from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class AutomationStep(BaseModel):
    """One PlanStep-shaped entry in a task_graph_template -- mirrors
    app/schemas/supervisor.py's PlanStep fields the template actually needs
    (status/execution_id/result/execution_time are runtime-only, not part
    of a template)."""
    step_id: str
    capability: str
    depends_on: list[str] = Field(default_factory=list)
    input_template: dict[str, Any] = Field(default_factory=dict)


class AutomationCreate(BaseModel):
    name: str = Field(..., min_length=1)
    trigger_type: str = Field(..., description="schedule | condition | event")
    schedule: Optional[str] = Field(default=None, description="Cron string, required for trigger_type=schedule")
    condition: Optional[dict[str, Any]] = Field(default=None, description="e.g. {'event_type': 'task_completed'}")
    steps: list[AutomationStep] = Field(..., min_length=1, description="The task_graph_template's steps")
    enabled: bool = Field(default=True)


class AutomationUpdate(BaseModel):
    name: Optional[str] = None
    schedule: Optional[str] = None
    condition: Optional[dict[str, Any]] = None
    steps: Optional[list[AutomationStep]] = None
    enabled: Optional[bool] = None


class AutomationResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    trigger_type: str
    schedule: Optional[str] = None
    condition: Optional[dict[str, Any]] = None
    steps: list[AutomationStep]
    enabled: bool
    execution_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AutomationRunResult(BaseModel):
    automation_id: str
    request_id: str
    status: str
    approval_id: Optional[int] = None
