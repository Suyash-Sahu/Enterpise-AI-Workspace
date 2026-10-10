"""
Calendar API Router (AMOF-X Phase 7).

Direct authenticated-user actions on their own calendar -- not a registered
TaskRegistry capability (unlike meeting.extract/workgraph.create_task), the
same way Drive browsing and Gmail draft creation are plain connector
endpoints rather than AI-invocable capabilities. Errors from
GoogleNotConnectedError/HTTPError are surfaced as real errors, never
fabricated data (same discipline as app/api/connectors.py).
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.connectors.google.exceptions import GoogleNotConnectedError
from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.calendar import EventCreate, EventUpdate
from app.services.calendar_service import CalendarService

router = APIRouter(prefix="/calendar", tags=["Calendar"])


def _connector_error(exc: Exception) -> HTTPException:
    """Same split as app/api/connectors.py's _connector_error: "no account
    connected" (fixed by connecting one) vs. "Google refused" (an upstream
    fault the caller can't fix by retrying) are distinct, not collapsed."""
    if isinstance(exc, GoogleNotConnectedError):
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No Google account is connected. Connect one to continue.",
        )
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Google request failed. Try reconnecting your account.",
    )


@router.get("/events")
def list_events(
    time_min: str = Query(..., description="RFC3339 datetime"),
    time_max: str = Query(..., description="RFC3339 datetime"),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        events = CalendarService.list_events(db=db, user_id=current_user.id, time_min=time_min, time_max=time_max, limit=limit)
    except Exception as exc:
        raise _connector_error(exc)
    return {"count": len(events), "events": events}


@router.post("/events", status_code=status.HTTP_201_CREATED)
def create_event(
    data: EventCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        event = CalendarService.create_event(
            db=db,
            user_id=current_user.id,
            summary=data.summary,
            start=data.start,
            end=data.end,
            description=data.description,
            attendees=data.attendees,
            add_meet=data.add_meet,
        )
    except Exception as exc:
        raise _connector_error(exc)
    return event


@router.patch("/events/{event_id}")
def update_event(
    event_id: str,
    data: EventUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        event = CalendarService.update_event(
            db=db, user_id=current_user.id, event_id=event_id,
            **data.model_dump(exclude_unset=True, exclude_none=True),
        )
    except Exception as exc:
        raise _connector_error(exc)
    return event


@router.get("/availability")
def check_availability(
    time_min: str = Query(..., description="RFC3339 datetime"),
    time_max: str = Query(..., description="RFC3339 datetime"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        busy = CalendarService.check_availability(db=db, user_id=current_user.id, time_min=time_min, time_max=time_max)
    except Exception as exc:
        raise _connector_error(exc)
    return {"busy": busy}
