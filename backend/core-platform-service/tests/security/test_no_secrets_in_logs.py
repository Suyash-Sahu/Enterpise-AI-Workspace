"""
AMOF-X Phase 10 Security & Observability Tests: No Secrets In Logs & Telemetry.

Verifies that model gateway requests, execution logs, and trace responses
do not log or expose API keys, bearer tokens, passwords, or secret headers.

Regression (Phase 9 audit): this test used to define its own throwaway
`sanitize_log_output`/`SECRET_PATTERNS` and test only that -- it never
imported anything from app/, so it passed unconditionally regardless of
whether the real logging pipeline redacted anything. It now exercises
`app.core.logging_config.RedactingFilter`, the actual filter installed on
every log handler in `configure_logging()`.
"""
import logging

from app.core.logging_config import RedactingFilter


def _filtered_message(raw: str) -> str:
    record = logging.LogRecord(
        name="test_no_secrets_in_logs",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=raw,
        args=(),
        exc_info=None,
    )
    RedactingFilter().filter(record)
    return record.getMessage()


def test_redacting_filter_strips_bearer_token_and_jwt():
    raw_log = (
        "Sending request with Authorization: Bearer "
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIn0.signaturepart"
    )
    message = _filtered_message(raw_log)

    assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in message
    assert "[REDACTED" in message


def test_redacting_filter_strips_api_key_value_pairs():
    raw_log = "Calling provider with OPENAI_API_KEY=sk-1234567890abcdef1234567890"
    message = _filtered_message(raw_log)

    assert "sk-1234567890abcdef1234567890" not in message
    assert "[REDACTED]" in message


def test_redacting_filter_strips_credentials_in_connection_url():
    raw_log = "Connecting to postgresql://postgres:supersecretpassword@localhost:5432/core_platform_db"
    message = _filtered_message(raw_log)

    assert "supersecretpassword" not in message
    assert "[REDACTED]" in message


def test_redacting_filter_leaves_ordinary_messages_untouched():
    raw_log = "Execution completed in 42ms for task_type=rag_answer"
    assert _filtered_message(raw_log) == raw_log
