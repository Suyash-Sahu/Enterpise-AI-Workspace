"""
Timezone-aware natural-language deadline parser for commitments.
Parses natural language strings ('Friday', 'Tomorrow', 'Next week', 'Within 2 days')
as well as explicit ISO and calendar dates into UTC datetimes.
"""
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from app.utils.timezone import resolve_timezone, to_utc, local_now


@dataclass
class ParsedDeadline:
    original_text: str
    normalized_dt: Optional[datetime]  # UTC datetime
    iso_string: Optional[str]  # e.g. "2026-11-06T18:00:00Z"
    confidence: float
    is_ambiguous: bool
    timezone_name: str


WEEKDAYS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
}

MONTHS = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}


def parse_deadline(
    text: Optional[str],
    user_tz: Optional[str] = "UTC",
    reference_dt: Optional[datetime] = None,
) -> ParsedDeadline:
    """
    Parses a deadline text string into a timezone-aware UTC datetime.
    """
    if not text or not text.strip():
        return ParsedDeadline(
            original_text="",
            normalized_dt=None,
            iso_string=None,
            confidence=0.0,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )

    raw = text.strip()
    clean = raw.lower()
    clean = re.sub(r"^(by|before|on|due|until|around|at)\s+", "", clean).strip()

    tz = resolve_timezone(user_tz)
    now = reference_dt or local_now(user_tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)

    # 1. Direct ISO format check
    try:
        # e.g. 2026-11-06 or 2026-11-06T17:00:00
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        utc_dt = to_utc(dt)
        return ParsedDeadline(
            original_text=raw,
            normalized_dt=utc_dt,
            iso_string=utc_dt.isoformat(),
            confidence=1.0,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )
    except ValueError:
        pass

    # 2. Relative keywords
    # "today", "eod", "end of day", "tonight"
    if clean in ("today", "eod", "end of today", "end of day", "tonight", "this evening"):
        target = now.replace(hour=18, minute=0, second=0, microsecond=0)
        utc_dt = to_utc(target)
        return ParsedDeadline(
            original_text=raw,
            normalized_dt=utc_dt,
            iso_string=utc_dt.isoformat(),
            confidence=0.95,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )

    # "tomorrow", "tomorrow morning", "tomorrow eod"
    if clean.startswith("tomorrow"):
        target = (now + timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        utc_dt = to_utc(target)
        return ParsedDeadline(
            original_text=raw,
            normalized_dt=utc_dt,
            iso_string=utc_dt.isoformat(),
            confidence=0.95,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )

    # "day after tomorrow"
    if "day after tomorrow" in clean:
        target = (now + timedelta(days=2)).replace(hour=18, minute=0, second=0, microsecond=0)
        utc_dt = to_utc(target)
        return ParsedDeadline(
            original_text=raw,
            normalized_dt=utc_dt,
            iso_string=utc_dt.isoformat(),
            confidence=0.95,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )

    # "within X days" or "in X days"
    m_days = re.search(r"(?:within|in)\s+(\d+)\s+days?", clean)
    if m_days:
        days = int(m_days.group(1))
        target = (now + timedelta(days=days)).replace(hour=18, minute=0, second=0, microsecond=0)
        utc_dt = to_utc(target)
        return ParsedDeadline(
            original_text=raw,
            normalized_dt=utc_dt,
            iso_string=utc_dt.isoformat(),
            confidence=0.90,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )

    # "within X hours" or "in X hours"
    m_hours = re.search(r"(?:within|in)\s+(\d+)\s+hours?", clean)
    if m_hours:
        hours = int(m_hours.group(1))
        target = now + timedelta(hours=hours)
        utc_dt = to_utc(target)
        return ParsedDeadline(
            original_text=raw,
            normalized_dt=utc_dt,
            iso_string=utc_dt.isoformat(),
            confidence=0.90,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )

    # "end of this week", "end of the week", "eow", "this weekend"
    if clean in ("end of this week", "end of week", "end of the week", "eow", "this weekend"):
        # Next Friday or Sunday at 18:00
        days_ahead = 4 - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        target = (now + timedelta(days=days_ahead)).replace(hour=18, minute=0, second=0, microsecond=0)
        utc_dt = to_utc(target)
        return ParsedDeadline(
            original_text=raw,
            normalized_dt=utc_dt,
            iso_string=utc_dt.isoformat(),
            confidence=0.88,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )

    # "end of this month", "end of the month", "eom"
    if clean in ("end of this month", "end of month", "end of the month", "eom"):
        next_month = now.replace(day=28) + timedelta(days=4)
        last_day = next_month - timedelta(days=next_month.day)
        target = last_day.replace(hour=18, minute=0, second=0, microsecond=0)
        utc_dt = to_utc(target)
        return ParsedDeadline(
            original_text=raw,
            normalized_dt=utc_dt,
            iso_string=utc_dt.isoformat(),
            confidence=0.90,
            is_ambiguous=False,
            timezone_name=user_tz or "UTC",
        )

    # "next <weekday>" or "this <weekday>" or simply "<weekday>"
    for w_name, w_idx in WEEKDAYS.items():
        if w_name in clean:
            is_next = "next" in clean
            current_w = now.weekday()
            days_ahead = (w_idx - current_w) % 7
            if days_ahead == 0 or is_next:
                days_ahead += 7
            target = (now + timedelta(days=days_ahead)).replace(hour=18, minute=0, second=0, microsecond=0)
            utc_dt = to_utc(target)
            return ParsedDeadline(
                original_text=raw,
                normalized_dt=utc_dt,
                iso_string=utc_dt.isoformat(),
                confidence=0.85,
                is_ambiguous=False,
                timezone_name=user_tz or "UTC",
            )

    # "Month Day" e.g. "November 5", "Nov 5th", "5 Nov"
    for m_name, m_num in MONTHS.items():
        pattern1 = rf"\b{m_name}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b"
        m1 = re.search(pattern1, clean)
        if m1:
            day = int(m1.group(1))
            year = int(m1.group(2)) if m1.group(2) else now.year
            try:
                target = datetime(year, m_num, day, 18, 0, 0, tzinfo=tz)
                if target < now and not m1.group(2):
                    target = datetime(year + 1, m_num, day, 18, 0, 0, tzinfo=tz)
                utc_dt = to_utc(target)
                return ParsedDeadline(
                    original_text=raw,
                    normalized_dt=utc_dt,
                    iso_string=utc_dt.isoformat(),
                    confidence=0.92,
                    is_ambiguous=False,
                    timezone_name=user_tz or "UTC",
                )
            except ValueError:
                pass

    # If parsing could not determine an exact date, mark as ambiguous
    return ParsedDeadline(
        original_text=raw,
        normalized_dt=None,
        iso_string=None,
        confidence=0.3,
        is_ambiguous=True,
        timezone_name=user_tz or "UTC",
    )

