"""
AMOF-X Phase 5: end-to-end proof that gmail.send cannot be reached without a
real, approved Approval record, and that approving one now actually results
in a real send (through the mocked GoogleConnectorService boundary) -- not
just a status flag flip.

Covers the two invariants this phase exists to prove:
1. No path from "drafted" to "sent" skips a real Approval row (draft ->
   reject -> no send; direct handler-call bypass -> refused).
2. Rejection is provably terminal, and approval is provably consumable
   exactly once (replay protection).
"""
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, engine
from app.schemas.approval import ApprovalCreate, ApprovalReject
from app.schemas.execution import ExecutionRequest
from app.services.approval.approval_service import approval_service
from app.services.execution_manager import execution_manager

OWNER_ID = "1"
WORKSPACE_ID = f"ws_user_{OWNER_ID}"

SEND_TARGET = "app.execution.contracts.GoogleConnectorService.send_email"


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _make_approval(db: Session, payload=None):
    data = ApprovalCreate(
        action_type="gmail.send",
        title="Send meeting update",
        description="test fixture",
        payload=payload or {"to": "rahul@example.com", "subject": "Update", "body": "Meeting moved."},
    )
    return approval_service.create_approval(db=db, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID, data=data)


def _exec_request(approval_id):
    return ExecutionRequest(
        task_type="gmail.send",
        input={"to": "ignored@example.com", "subject": "ignored", "body": "ignored"},
        approval_id=approval_id,
    )


def test_direct_bypass_without_any_approval_is_refused():
    """The defense-in-depth gate itself: no approval_id at all."""
    db = SessionLocal()
    try:
        with patch(SEND_TARGET) as mock_send:
            req = ExecutionRequest(
                task_type="gmail.send",
                input={"to": "x@example.com", "subject": "x", "body": "x"},
                approval_id=None,
            )
            res = execution_manager.execute(db=db, request=req, owner_id=OWNER_ID)
        assert res.status.value == "FAILED"
        assert "approval" in (res.error_message or "").lower()
        mock_send.assert_not_called()
    finally:
        db.close()


def test_pending_unapproved_approval_is_refused():
    """An approval that exists but was never approved must not authorize a send."""
    db = SessionLocal()
    try:
        approval = _make_approval(db)
        with patch(SEND_TARGET) as mock_send:
            res = execution_manager.execute(db=db, request=_exec_request(approval.id), owner_id=OWNER_ID)
        assert res.status.value == "FAILED"
        mock_send.assert_not_called()
    finally:
        db.close()


def test_rejected_approval_is_provably_terminal():
    """draft -> reject -> no send occurs, even if execution is attempted anyway."""
    db = SessionLocal()
    try:
        approval = _make_approval(db)
        approval_service.reject(
            db=db, approval_id=approval.id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID,
            data=ApprovalReject(reason="not needed"),
        )
        with patch(SEND_TARGET) as mock_send:
            res = execution_manager.execute(db=db, request=_exec_request(approval.id), owner_id=OWNER_ID)
        assert res.status.value == "FAILED"
        mock_send.assert_not_called()
    finally:
        db.close()


def test_approved_path_sends_exactly_once_and_completes():
    """draft -> approve -> execute -> real send occurs, Approval reaches 'completed'."""
    db = SessionLocal()
    try:
        approval = _make_approval(db, payload={"to": "dev@example.com", "subject": "Build OK", "body": "Passed"})
        approval_service.approve(db=db, approval_id=approval.id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID)

        with patch(SEND_TARGET, return_value={"id": "msg_123"}) as mock_send:
            res = execution_manager.execute(db=db, request=_exec_request(approval.id), owner_id=OWNER_ID)

        assert res.status.value == "COMPLETED"
        mock_send.assert_called_once()
        _, kwargs = mock_send.call_args
        # The APPROVED payload was used, not whatever ExecutionRequest.input said.
        assert kwargs["to"] == "dev@example.com"
        assert kwargs["subject"] == "Build OK"

        refreshed = approval_service.get_approval(db=db, approval_id=approval.id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID)
        assert refreshed.status == "completed"
    finally:
        db.close()


def test_approved_edited_payload_wins_over_original():
    """An edited payload (reviewed before approval) is what actually gets sent."""
    db = SessionLocal()
    try:
        approval = _make_approval(db, payload={"to": "original@example.com", "subject": "Original", "body": "Original"})
        from app.schemas.approval import ApprovalEdit
        approval_service.edit(
            db=db, approval_id=approval.id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID,
            data=ApprovalEdit(edited_payload={"to": "edited@example.com", "subject": "Edited", "body": "Edited"}),
        )
        approval_service.approve(db=db, approval_id=approval.id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID)

        with patch(SEND_TARGET, return_value={"id": "msg_456"}) as mock_send:
            execution_manager.execute(db=db, request=_exec_request(approval.id), owner_id=OWNER_ID)

        _, kwargs = mock_send.call_args
        assert kwargs["to"] == "edited@example.com"
        assert kwargs["subject"] == "Edited"
    finally:
        db.close()


def test_same_approval_cannot_be_consumed_twice():
    """Replay protection: a second execute attempt against a completed approval is refused."""
    db = SessionLocal()
    try:
        approval = _make_approval(db)
        approval_service.approve(db=db, approval_id=approval.id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID)

        with patch(SEND_TARGET, return_value={"id": "msg_789"}) as mock_send:
            first = execution_manager.execute(db=db, request=_exec_request(approval.id), owner_id=OWNER_ID)
            assert first.status.value == "COMPLETED"

            second = execution_manager.execute(db=db, request=_exec_request(approval.id), owner_id=OWNER_ID)
            assert second.status.value == "FAILED"

        assert mock_send.call_count == 1
    finally:
        db.close()


def test_wrong_action_type_approval_cannot_authorize_gmail_send():
    """An approval for a different action_type must not authorize gmail.send."""
    db = SessionLocal()
    try:
        data = ApprovalCreate(
            action_type="calendar.create",
            title="Schedule meeting",
            payload={"summary": "Standup"},
        )
        approval = approval_service.create_approval(db=db, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID, data=data)
        approval_service.approve(db=db, approval_id=approval.id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID)

        with patch(SEND_TARGET) as mock_send:
            res = execution_manager.execute(db=db, request=_exec_request(approval.id), owner_id=OWNER_ID)
        assert res.status.value == "FAILED"
        mock_send.assert_not_called()
    finally:
        db.close()


def test_supervisor_originated_approval_is_now_actually_executable():
    """
    End-to-end: a Supervisor run pauses on gmail.send exactly like before,
    but approving that same Approval and then calling the generic
    POST /approvals/{id}/execute path (exercised here via execution_manager,
    which is what that endpoint calls) now results in a real send -- this is
    the gap Phase 5 closes: previously, approving a Supervisor-originated
    approval changed a status flag and nothing else.
    """
    from app.supervisor.context import SupervisorContext
    from app.supervisor.supervisor import amof_supervisor

    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id=OWNER_ID,
            question="send an email notice to user",
            hitl_enabled=True,
            verification_enabled=False,
        )
        paused = amof_supervisor.run(db=db, context=context)
        assert paused.status == "WAITING_FOR_APPROVAL"
        assert paused.approval_id is not None

        approval_service.approve(
            db=db, approval_id=paused.approval_id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID,
        )

        with patch(SEND_TARGET, return_value={"id": "msg_supervisor"}) as mock_send:
            res = execution_manager.execute(db=db, request=_exec_request(paused.approval_id), owner_id=OWNER_ID)

        assert res.status.value == "COMPLETED"
        mock_send.assert_called_once()
    finally:
        db.close()
