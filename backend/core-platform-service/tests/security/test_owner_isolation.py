"""
AMOF-X Phase 9 Security Hardening: per-owner data isolation tests.

Renamed from test_rbac_matrix.py in Phase 20: the file never contained a
role/permission matrix, and the name overstated what the system does. What
it verifies -- and what the system actually implements -- is per-owner data
isolation across platform services (ExecutionManager, ApprovalService,
WorkGraphService): User B cannot read, modify, or act on resources owned by
User A. Role-based authorization exists only as require_role("admin") on the
admin routes (app/core/rbac.py), not as a general permission matrix, and
there is no tenant/organization entity in the codebase at all -- workspace_id
is a synthetic per-user string. See docs/CURRENT_STATE.md.
"""
from unittest.mock import patch
import pytest
from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, engine
from app.models.approval import Approval
from app.schemas.approval import ApprovalCreate
from app.schemas.execution import ExecutionRequest
from app.services.approval.approval_service import approval_service
from app.services.execution_manager import execution_manager
from app.services.workgraph_service import workgraph_service

from app.models.user import User
from app.models.role import Role
from app.db.seed import seed_roles

USER_A = "1"
USER_B = "2"
WORKSPACE_A = f"ws_user_{USER_A}"
WORKSPACE_B = f"ws_user_{USER_B}"


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_roles(db)
        role = db.query(Role).filter(Role.name == "user").first()
        if not db.query(User).filter(User.id == int(USER_A)).first():
            db.add(User(id=int(USER_A), name="User A", email="user_a@example.com", password_hash="hash", role_id=role.id))
        if not db.query(User).filter(User.id == int(USER_B)).first():
            db.add(User(id=int(USER_B), name="User B", email="user_b@example.com", password_hash="hash", role_id=role.id))
        db.commit()
    finally:
        db.close()
    yield


@patch("app.execution.contracts.runtime_service.generate")
def test_execution_manager_owner_isolation(mock_generate):
    """
    User B cannot retrieve execution status of User A's execution,
    and get_history for User B never leaks User A's executions.
    """
    from app.schemas.runtime import RuntimeGenerateResponse
    mock_generate.return_value = RuntimeGenerateResponse(
        completion="Mock completion", provider="mock", model="mock", runtime="cloud"
    )

    db = SessionLocal()
    try:
        req = ExecutionRequest(
            task_type="text_generation",
            input={"prompt": "Owner isolation test prompt"},
            execution_mode="cloud",
        )
        res_a = execution_manager.execute(db=db, request=req, owner_id=USER_A)
        assert res_a.status.value == "COMPLETED"

        # User B attempts to access User A's execution status
        with pytest.raises(ValueError, match="not found or access denied"):
            execution_manager.get_status(db=db, execution_id=res_a.execution_id, owner_id=USER_B)

        # User B gets history; User A's execution must NOT be present
        history_b = execution_manager.get_history(db=db, owner_id=USER_B)
        execution_ids_b = [item.execution_id for item in history_b.items]
        assert res_a.execution_id not in execution_ids_b

    finally:
        db.close()


def test_approval_service_owner_isolation():
    """
    User B cannot access or approve/reject User A's approval record.
    """
    db = SessionLocal()
    try:
        approval_data = ApprovalCreate(
            action_type="gmail.send",
            title="User A Email",
            description="Private action for User A",
            payload={"to": "secret@example.com", "subject": "Private", "body": "Secret"},
        )
        approval_a = approval_service.create_approval(
            db=db, user_id=int(USER_A), workspace_id=WORKSPACE_A, data=approval_data
        )

        # User B attempts to fetch User A's approval record
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            approval_service.get_approval(db=db, approval_id=approval_a.id, user_id=int(USER_B), workspace_id=WORKSPACE_B)
        assert exc_info.value.status_code == 404

        # User B attempts to approve User A's approval record
        with pytest.raises(HTTPException) as exc_info_approve:
            approval_service.approve(db=db, approval_id=approval_a.id, user_id=int(USER_B), workspace_id=WORKSPACE_B)
        assert exc_info_approve.value.status_code == 404

    finally:
        db.close()


def test_workgraph_task_owner_isolation():
    """
    User B cannot query or access WorkGraph tasks belonging to User A.
    """
    db = SessionLocal()
    try:
        task_a = workgraph_service.create_task(
            db=db,
            owner_id=USER_A,
            title="User A Confidential Task",
            description="Confidential",
        )

        # WorkGraph list for User B must not include User A's task
        tasks_b = workgraph_service.list_tasks(db=db, owner_id=USER_B)
        task_ids_b = [t.id for t in tasks_b]
        assert task_a.id not in task_ids_b

    finally:
        db.close()
