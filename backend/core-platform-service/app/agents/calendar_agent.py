"""
CalendarAgent (Phase 23): time and availability reasoning.

Tools: CalendarService.list_events/check_availability -- a thin read-only
wrapper, no new Calendar integration. Conflict detection reuses the same
pairwise-overlap logic app/execution/contracts.py's DigestHandler already
relied on (_detect_conflicts), moved here so DigestHandler can delegate to
this agent instead of embedding the calendar-reading logic itself.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agents.base import Agent, AgentContext, AgentResult, AgentSpec
from app.services.calendar_service import CalendarService

logger = logging.getLogger(__name__)


class CalendarViewInput(BaseModel):
    time_min: str
    time_max: str
    limit: int = 20


class ScheduleView(BaseModel):
    events: list[dict] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
    free_blocks: list[dict] = Field(default_factory=list)
    capacity_by_day: dict[str, int] = Field(default_factory=dict)


def _event_bounds(event: dict[str, Any]) -> tuple[Optional[datetime], Optional[datetime]]:
    def parse(side: str) -> Optional[datetime]:
        raw = (event.get(side) or {}).get("dateTime")
        if not raw:
            return None
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None

    return parse("start"), parse("end")


def _detect_conflicts(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Pairwise overlap over timed events. O(n^2): a single day's events for one
    user is a handful of items, and the sorted sweep that would beat it is
    more code to get wrong for no measurable gain.
    """
    timed = []
    for event in events:
        start, end = _event_bounds(event)
        if start and end:
            timed.append((start, end, event))

    conflicts = []
    for i in range(len(timed)):
        for j in range(i + 1, len(timed)):
            a_start, a_end, a = timed[i]
            b_start, b_end, b = timed[j]
            if a_start < b_end and b_start < a_end:
                conflicts.append({
                    "event_a": a.get("summary", "(no title)"),
                    "event_b": b.get("summary", "(no title)"),
                })
    return conflicts


class CalendarAgent(Agent):
    spec = AgentSpec(
        name="CalendarAgent",
        role="time and availability reasoning",
        input_schema=CalendarViewInput,
        output_schema=ScheduleView,
        tools=["CalendarService"],
        reads_state=["owner_id"],
        writes_state=[],
        side_effect="read_only",
        requires_human_approval=False,
        verifier="ScheduleVerifier",
    )

    def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
        assert isinstance(inputs, CalendarViewInput)
        try:
            user_id = int(ctx.owner_id)
        except (TypeError, ValueError):
            raise ValueError(
                f"owner_id {ctx.owner_id!r} is not a users.id, so this calendar "
                "read cannot be scoped to a real account's connector."
            ) from None

        events = CalendarService.list_events(
            db=ctx.db, user_id=user_id,
            time_min=inputs.time_min, time_max=inputs.time_max, limit=inputs.limit,
        )
        conflicts = _detect_conflicts(events)
        view = ScheduleView(
            events=list(events),
            conflicts=conflicts,
            free_blocks=[],  # not computed pre-Phase-23 either; left empty rather than guessed
            capacity_by_day={},
        )
        return AgentResult(output=view, evidence=[str(e.get("summary")) for e in events])


calendar_agent = CalendarAgent()
