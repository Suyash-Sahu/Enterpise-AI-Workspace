"""Digest-specific email grouping, categorization and metadata normalization."""
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any, Optional

from app.utils.timezone import local_now, resolve_timezone


def parse_email_datetime(ts_raw: Any, user_tz_id: Optional[str] = None) -> Optional[datetime]:
    """Parse integer epoch ms, RFC 2822 date header, or ISO datetime into user's timezone."""
    if not ts_raw:
        return None
    tz = resolve_timezone(user_tz_id)
    try:
        if isinstance(ts_raw, (int, float)) or (isinstance(ts_raw, str) and ts_raw.isdigit()):
            ts = float(ts_raw)
            # If timestamp is in milliseconds (typical Gmail internalDate > 10^11)
            if ts > 10_000_000_000:
                ts = ts / 1000.0
            return datetime.fromtimestamp(ts, tz=tz)
        if isinstance(ts_raw, str):
            try:
                dt = parsedate_to_datetime(ts_raw)
                return dt.astimezone(tz)
            except Exception:
                pass
            try:
                dt = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    return dt.replace(tzinfo=tz)
                return dt.astimezone(tz)
            except Exception:
                pass
    except Exception:
        pass
    return None


def categorize_email_by_date(
    msg: dict[str, Any],
    user_tz_id: Optional[str] = None,
) -> str:
    """Return 'today' | 'yesterday' | 'older'. Uses internal received timestamp or date header."""
    ts_raw = msg.get("internalDate") or msg.get("received_at") or msg.get("date")
    msg_dt = parse_email_datetime(ts_raw, user_tz_id)

    if msg_dt is None:
        return "older"

    now_local = local_now(user_tz_id)
    today_start = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start + timedelta(days=1)
    yesterday_start = today_start - timedelta(days=1)

    if today_start <= msg_dt < today_end:
        return "today"
    if yesterday_start <= msg_dt < today_start:
        return "yesterday"
    return "older"


def normalize_email_meta(msg: dict[str, Any], user_tz_id: Optional[str] = None) -> dict[str, Any]:
    """Return normalized metadata for digest display with priority, sender, and status flags."""
    labels = msg.get("labelIds") or msg.get("labels") or []
    if isinstance(labels, str):
        labels = [labels]
    
    is_important = bool(
        "IMPORTANT" in labels
        or msg.get("is_important")
        or msg.get("label") == "urgent"
        or msg.get("priority") in ("urgent", "high")
    )
    is_unread = bool("UNREAD" in labels or msg.get("is_unread", True))

    ts_raw = msg.get("internalDate") or msg.get("received_at") or msg.get("date")
    parsed_dt = parse_email_datetime(ts_raw, user_tz_id)
    received_iso = parsed_dt.isoformat() if parsed_dt else (str(ts_raw) if ts_raw else None)

    sender = msg.get("from") or msg.get("sender") or "Unknown"
    # Clean sender name from "Name <email@domain>" format if possible
    sender_name = sender
    sender_email = sender
    if "<" in sender and ">" in sender:
        parts = sender.split("<")
        sender_name = parts[0].strip().strip('"') or parts[1].strip(">")
        sender_email = parts[1].strip(">").strip()

    subject = msg.get("subject") or msg.get("snippet", "")[:60] or "(No Subject)"

    return {
        "id": msg.get("id"),
        "thread_id": msg.get("threadId") or msg.get("thread_id"),
        "subject": subject,
        "sender": sender_name,
        "sender_email": sender_email,
        "received_at": received_iso,
        "snippet": msg.get("snippet", ""),
        "labels": labels,
        "is_important": is_important,
        "is_unread": is_unread,
        "classification": msg.get("label") or msg.get("classification") or "unclassified",
        "priority": msg.get("priority") or ("urgent" if is_important else "normal"),
    }

