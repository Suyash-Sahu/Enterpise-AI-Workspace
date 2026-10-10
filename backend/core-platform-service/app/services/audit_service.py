"""
Audit trail (AMOF-X Phase 20).

Two mechanisms used to exist side by side: `approval_events` (written on
every approval lifecycle transition by approval_audit.log_event) and this
`audit_logs` table, which only a manual `POST /audit-log/` endpoint ever
wrote -- and which took the action string from the caller. A side-effecting
execution that was not approval-gated therefore left no audit row at all,
so "comprehensive audit logging" was not a claim the code supported.

log_execution below closes that gap: the executor calls it exactly once per
side-effecting execution (see ExecutionExecutor), with the action derived
from the registered capability rather than supplied by the caller.
"""
import logging

from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def log_action(
    db: Session,
    user_id: int,
    action: str,
    endpoint: str,
    method: str,
):
    log = AuditLog(
        user_id=user_id,
        action=action,
        endpoint=endpoint,
        method=method,
    )

    db.add(log)
    db.commit()


def log_execution(db: Session, owner_id: str, execution_id: str, task_type: str, status: str) -> None:
    """
    Records one audit row for one side-effecting execution.

    Never raises. The Execution row is already committed by the time this
    runs, so a failed audit write must not turn a completed side effect into
    a reported failure -- but it must be loud, not silent, hence the
    exception log. Callers that need the guarantee assert on the rows
    (tests/test_audit_coverage.py), not on this function's return.
    """
    try:
        user_id = int(owner_id)
    except (TypeError, ValueError):
        logger.error(
            "[Audit] execution %s (%s) has non-numeric owner_id %r; no audit row written.",
            execution_id, task_type, owner_id,
        )
        return

    try:
        log_action(
            db=db,
            user_id=user_id,
            action=f"execution.{task_type}:{status}",
            endpoint=f"/execution/{execution_id}",
            method="EXECUTE",
        )
    except Exception:
        db.rollback()
        logger.exception(
            "[Audit] failed to write audit row for execution %s (%s).", execution_id, task_type
        )
