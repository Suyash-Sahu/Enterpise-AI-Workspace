from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


DependencyKind = Literal["BLOCKS", "BLOCKED_BY", "RELATES_TO"]


class DependencyCreate(BaseModel):
    # Field name kept for backward compatibility: it is the *other* task.
    # kind=BLOCKED_BY (default): task_id is blocked by other. BLOCKS: task_id
    # blocks other. RELATES_TO: informational link, never blocks.
    depends_on_task_id: str = Field(
        min_length=1,
        description="The other task in the relationship",
    )
    kind: DependencyKind = "BLOCKED_BY"


class DependencyResponse(BaseModel):
    task_id: str
    depends_on_task_id: str
    kind: str = "BLOCKED_BY"


# ---------------------------------------------------------------------------
# Shared values
# ---------------------------------------------------------------------------

WorkStatus = Literal[
    "backlog",
    "open",
    "todo",
    "in_progress",
    "in_review",
    "blocked",
    "done",
    "cancelled",
]

WorkPriority = Literal[
    "low",
    "medium",
    "high",
    "urgent",
]

CreatedBy = Literal["human", "ai"]

SourceType = Literal[
    "user_request",
    "meeting_action_item",
    "cdrp_replan",
    "manual",
    "ai_proposal",
    "automation",
]

WorkType = Literal["TASK", "BUG", "FEATURE"]


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Project name",
    )
    description: Optional[str] = Field(
        default=None,
        description="Project description",
    )


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    description: Optional[str] = None
    status: Optional[str] = None


class ProjectResponse(BaseModel):
    id: str
    owner_id: str
    name: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Work items
# ---------------------------------------------------------------------------

class TaskCreate(BaseModel):
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Work item title",
    )

    description: Optional[str] = Field(
        default=None,
        description="Work item description",
    )

    project_id: Optional[str] = Field(
        default=None,
        description="Parent project",
    )

    assignee: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    priority: WorkPriority = Field(
        default="medium",
    )

    status: WorkStatus = Field(
        default="open",
    )

    type: WorkType = "TASK"

    due_date: Optional[datetime] = Field(
        default=None,
    )

    depends_on: list[str] = Field(
        default_factory=list,
        description="Task IDs this task depends on",
    )


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
    )

    description: Optional[str] = None

    assignee: Optional[str] = Field(
        default=None,
        max_length=255,
    )

    priority: Optional[WorkPriority] = None

    status: Optional[WorkStatus] = None

    type: Optional[WorkType] = None

    due_date: Optional[datetime] = None


class TaskResponse(BaseModel):
    id: str
    owner_id: str
    project_id: Optional[str] = None

    title: str
    description: Optional[str] = None

    assignee: Optional[str] = None

    priority: WorkPriority
    status: WorkStatus

    due_date: Optional[datetime] = None

    type: str = "TASK"

    created_by: CreatedBy
    created_by_actor: Optional[str] = None
    source_type: SourceType
    source_ref: Optional[str] = None
    ai_confidence: Optional[float] = None

    depends_on: list[str] = Field(
        default_factory=list,
    )

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ActivityResponse(BaseModel):
    id: int
    task_id: str
    actor: str
    event_type: str
    payload: Optional[dict] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LinksResponse(BaseModel):
    blocked_by: list[str] = Field(default_factory=list)
    blocks: list[str] = Field(default_factory=list)
    relates_to: list[str] = Field(default_factory=list)


class StatusCounts(BaseModel):
    open: int = 0
    in_progress: int = 0
    blocked: int = 0
    done: int = 0


class ProjectStats(BaseModel):
    project_id: str
    total: int
    counts: StatusCounts
    overdue: int


class DashboardResponse(BaseModel):
    counts: StatusCounts
    due_today: list[TaskResponse]
    overdue: list[TaskResponse]
    recently_updated: list[TaskResponse]


class BoardResponse(BaseModel):
    project_id: str
    columns: dict[str, list[TaskResponse]]


# ---------------------------------------------------------------------------
# Comments (single-owner; author is always server-derived)
# ---------------------------------------------------------------------------

class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class CommentUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class CommentResponse(BaseModel):
    id: str
    task_id: str
    author: str
    body: str
    edited: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
