"""Timezone utilities for Morning Brief and digest execution."""
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

VALID_TZ_IDS = {
    "Asia/Kolkata", "Asia/Singapore", "Europe/London", "America/New_York",
    "UTC", "US/Eastern", "US/Central", "US/Pacific", "Europe/Berlin",
    "Australia/Sydney", "Japan", "Asia/Dubai"
}

DEFAULT_TZ = "UTC"


def resolve_timezone(user_tz: Optional[str]) -> timezone | ZoneInfo:
    tz_str = (user_tz or DEFAULT_TZ).strip()
    if tz_str == "UTC":
        return timezone.utc
    try:
        return ZoneInfo(tz_str)
    except (ZoneInfoNotFoundError, Exception):
        return timezone.utc



def local_now(tz_id: Optional[str] = None) -> datetime:
    tz = resolve_timezone(tz_id)
    return datetime.now(tz)


def local_day_start(tz_id: Optional[str] = None) -> datetime:
    now = local_now(tz_id)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def local_day_end(tz_id: Optional[str] = None) -> datetime:
    start = local_day_start(tz_id)
    return start + timedelta(days=1)


def to_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
