from typing import Optional
from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    summary: str = Field(..., min_length=1)
    start: str = Field(..., description="RFC3339 datetime, e.g. 2026-09-20T10:00:00Z")
    end: str = Field(..., description="RFC3339 datetime")
    description: str = Field(default="")
    attendees: list[str] = Field(default_factory=list, description="Attendee email addresses")
    add_meet: bool = Field(default=False, description="Request a real Google Meet conference link")


class EventUpdate(BaseModel):
    summary: Optional[str] = None
    description: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None
