"""
Logging setup.

Two things matter here: a consistent format across the app's own loggers and
its dependencies, and a filter that redacts credentials before they reach a
log file. Nothing should ever log a token or a password, but a defence that
only works when every call site remembers is not a defence.
"""

import logging
import re
import sys
from typing import Any

from app.core.config import settings

# Patterns are matched against the *formatted* message, so they catch both
# f-string interpolation and %-style args.
_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    # Bearer <token>
    (re.compile(r"(?i)\b(bearer\s+)[A-Za-z0-9._\-]{8,}"), r"\1[REDACTED]"),
    # Any three-part JWT
    (
        re.compile(r"\beyJ[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}\.[A-Za-z0-9_\-]{5,}"),
        "[REDACTED_JWT]",
    ),
    # key=value / "key": "value" for sensitive names -- (?:\b|(?<=_)) rather
    # than a plain \b so a prefixed env-var-style name like OPENAI_API_KEY or
    # GOOGLE_CLIENT_SECRET still matches: \b alone fails there because "_" is
    # a word character, so there is no boundary between the prefix and the
    # keyword (caught by tests/security/test_no_secrets_in_logs.py).
    (
        re.compile(
            r"(?i)(?:\b|(?<=_))(password|passwd|secret|token|api_?key|authorization|"
            r"client_secret|refresh_token|access_token|code_verifier)"
            r"(\"?\s*[:=]\s*\"?)([^\s,;\"'}\)]{3,})"
        ),
        r"\1\2[REDACTED]",
    ),
    # Credentials embedded in a connection URL
    (
        re.compile(r"(?i)(://[^\s:/@]+:)([^\s@/]{2,})(@)"),
        r"\1[REDACTED]\3",
    ),
]


class RedactingFilter(logging.Filter):
    """Strips credential-shaped substrings from every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            return True

        redacted = message
        for pattern, replacement in _REDACTIONS:
            redacted = pattern.sub(replacement, redacted)

        if redacted != message:
            # Replace the whole message and drop args, which have already been
            # folded into it by getMessage().
            record.msg = redacted
            record.args = ()

        return True


class JsonFormatter(logging.Formatter):
    """Minimal JSON lines, for when logs are shipped rather than read."""

    def format(self, record: logging.LogRecord) -> str:
        import json

        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging() -> None:
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RedactingFilter())

    if settings.LOG_JSON:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)

    # uvicorn installs its own handlers; route them through ours so the
    # redaction filter applies to request logs too.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uv = logging.getLogger(name)
        uv.handlers.clear()
        uv.propagate = True

    # SQLAlchemy echoes full statements at INFO, which can include bound values.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
