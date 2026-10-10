"""Time helpers."""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """Timezone-aware current UTC time. Use for `DateTime(timezone=True)`."""
    return datetime.now(timezone.utc)


def utcnow_naive() -> datetime:
    """
    Current UTC time with the tzinfo stripped.

    Exact drop-in for the deprecated `datetime.utcnow()`. Used by the
    evaluation subsystem, whose columns are plain `DateTime` — writing an
    aware value into a naive column is what causes the comparisons to go wrong,
    so the naive-ness is preserved deliberately rather than half-migrated.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
