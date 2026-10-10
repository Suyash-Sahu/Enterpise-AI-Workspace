"""
Phase 20: every side-effecting execution produces exactly one audit_logs row.

"Side-effecting" is read from each capability's own CapabilityMetadata, so a
capability added later is covered by this test the day it is registered --
the same live-registry discipline the approval-bypass sweep uses.
"""
from unittest.mock import patch

import pytest

from app.db.database import Base, SessionLocal, engine
from app.db.seed import seed_roles
from app.execution.registry import task_registry
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.user import User
from app.schemas.execution import ExecutionRequest
from app.schemas.runtime import RuntimeGenerateResponse
from app.services.execution_manager import execution_manager

OWNER_ID = "1"

def _execute(request, owner_id=OWNER_ID):
    """Execute on a session that is always closed -- the executor does not
    close the Session it is handed, so an inline SessionLocal() leaks a
    pooled connection per call and the pool runs out mid-suite."""
    db = SessionLocal()
    try:
        return execution_manager.execute(db=db, request=request, owner_id=owner_id)
    finally:
        db.close()



@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_roles(db)
        role = db.query(Role).filter(Role.name == "user").first()
        if not db.query(User).filter(User.id == int(OWNER_ID)).first():
            db.add(User(
                id=int(OWNER_ID), name="Audit Test User",
                email="audit_user@example.com", password_hash="hash", role_id=role.id,
            ))
            db.commit()
    finally:
        db.close()
    yield


def _audit_rows(execution_id: str) -> list[AuditLog]:
    db = SessionLocal()
    try:
        return db.query(AuditLog).filter(AuditLog.endpoint == f"/execution/{execution_id}").all()
    finally:
        db.close()


def test_side_effecting_capabilities_exist():
    side_effecting = [
        t for t in task_registry.list_supported_tasks()
        if task_registry.get_metadata(t).side_effect != "read_only"
    ]
    assert side_effecting, "expected at least one side-effecting capability (e.g. gmail.send)"


def test_successful_side_effecting_execution_writes_exactly_one_audit_row():
    """workgraph.create_task: a real write, and the one that needs no approval."""
    req = ExecutionRequest(
        task_type="workgraph.create_task",
        input={"title": "Phase 20 audit coverage task"},
    )
    res = _execute(req, owner_id=OWNER_ID)
    assert res.status.value == "COMPLETED", res.error_message

    rows = _audit_rows(res.execution_id)
    assert len(rows) == 1, f"expected exactly 1 audit row, got {len(rows)}"
    assert rows[0].action == "execution.workgraph.create_task:COMPLETED"
    assert rows[0].user_id == int(OWNER_ID)


def test_failed_side_effecting_execution_is_audited_exactly_once():
    """A refused gmail.send (no approval) is an attempt, and attempts are audited."""
    req = ExecutionRequest(
        task_type="gmail.send",
        input={"to": "x@example.test", "subject": "x", "body": "x"},
        approval_id=None,
    )
    res = _execute(req, owner_id=OWNER_ID)
    assert res.status.value == "FAILED"

    rows = _audit_rows(res.execution_id)
    assert len(rows) == 1, f"expected exactly 1 audit row, got {len(rows)}"
    assert rows[0].action == "execution.gmail.send:FAILED"


@patch("app.execution.contracts.runtime_service.generate")
def test_read_only_execution_writes_no_audit_row(mock_generate):
    """
    The trail records side effects. Auditing every read too would bury them
    and is not what this phase claims -- the claim in the docs must match.
    """
    mock_generate.return_value = RuntimeGenerateResponse(
        completion="hello", provider="mock", model="mock", runtime="local",
    )
    req = ExecutionRequest(
        task_type="text_generation",
        input={"prompt": "audit coverage read-only check"},
        metadata={"cache_enabled": False},
    )
    res = _execute(req, owner_id=OWNER_ID)
    assert res.status.value == "COMPLETED", res.error_message
    assert _audit_rows(res.execution_id) == []
