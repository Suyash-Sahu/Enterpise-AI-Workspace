from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class MeetingCreate(BaseModel):
    transcript_text: str = Field(..., min_length=1, description="Raw transcript text (upload/export/paste)")
    transcript_source: str = Field(
        default="manual_paste",
        description="upload | note_taking_export | manual_paste -- no live Google Meet API pull exists",
    )


class ActionItemResponse(BaseModel):
    id: str
    description: str
    owner: Optional[str] = None
    due_date: Optional[str] = None
    workgraph_task_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class MeetingResponse(BaseModel):
    id: str
    owner_id: str
    transcript_source: str
    status: str
    summary: Optional[str] = None
    decisions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    unresolved_questions: list[str] = Field(default_factory=list)
    action_items: list[ActionItemResponse] = Field(default_factory=list)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CreateTaskFromActionItemRequest(BaseModel):
    project_id: Optional[str] = Field(default=None)
    assignee: Optional[str] = Field(default=None)
    priority: str = Field(default="medium")


class BulkCreateTasksFromActionItemsRequest(BaseModel):
    project_id: Optional[str] = Field(default=None)
    priority: str = Field(default="medium")


class BulkCreateTaskResult(BaseModel):
    item_id: str
    status: str  # "created" | "skipped_already_linked" | "failed"
    task_id: Optional[str] = None
    error: Optional[str] = None


class BulkCreateTasksResponse(BaseModel):
    results: list[BulkCreateTaskResult]
