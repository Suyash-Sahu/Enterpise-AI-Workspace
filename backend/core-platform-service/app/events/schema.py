"""
Event schema (AMOF-X Phase 8): covers target spec §22's lifecycle-event
list. One flat Event envelope, not a type hierarchy -- the payload dict
carries whatever fields a given event_type needs, matching how every other
capability's `input_data`/`result` dict in this codebase is shaped.
"""
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class EventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    VERIFICATION_COMPLETED = "verification_completed"
    STEP_VERIFICATION_COMPLETED = "step_verification_completed"  # Phase 29
    REPLANNING_REQUESTED = "replanning_requested"
    APPROVAL_REQUESTED = "approval_requested"
    APPROVAL_GRANTED = "approval_granted"
    APPROVAL_REJECTED = "approval_rejected"


class Event(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    event_type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)
    trace_id: Optional[str] = None
    owner_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
