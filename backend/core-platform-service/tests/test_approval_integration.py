"""
Project 8 — End-to-End Approval & HITL Integration Test Suite
Tests Gmail side-effect endpoint protection, unapproved 403 rejection,
approved execution consumption, replay prevention, and P7 AMOF Supervisor HITL pause flow.
"""

import pytest
from sqlalchemy.orm import Session

from app.core.dependencies import get_db
from app.models.approval import Approval
from app.schemas.approval import ApprovalCreate
from app.services.approval.approval_service import approval_service
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor


def test_gmail_send_requires_authentication(client):
    """An anonymous caller must not reach the send endpoint at all."""
    response = client.post(
        "/api/v1/connectors/google/gmail/send",
        json={"to": "test@example.com", "subject": "x", "body": "y"},
    )
    assert response.status_code == 401


def test_gmail_send_blocked_without_approval_id(auth_client):
    """Verify POST /api/v1/connectors/google/gmail/send returns 403 without approval_id."""
    payload = {
        "to": "test@example.com",
        "subject": "Unauthorized email",
        "body": "This should be blocked",
    }
    response = auth_client.post("/api/v1/connectors/google/gmail/send", json=payload)
    assert response.status_code == 403
    assert "approval record is required" in response.json()["detail"]


def test_gmail_send_blocked_with_pending_approval(auth_client, test_user):
    """Verify POST /api/v1/connectors/google/gmail/send returns 403 when approval is still pending."""
    db: Session = next(get_db())
    user_id = test_user.id
    workspace_id = f"ws_user_{user_id}"

    approval = approval_service.create_approval(
        db=db,
        user_id=user_id,
        workspace_id=workspace_id,
        data=ApprovalCreate(
            action_type="gmail.send",
            title="Pending test email",
            payload={"to": "test@example.com", "subject": "Test", "body": "Body"},
        ),
    )

    payload = {
        "to": "test@example.com",
        "subject": "Test",
        "body": "Body",
        "approval_id": approval.id,
    }
    response = auth_client.post("/api/v1/connectors/google/gmail/send", json=payload)
    assert response.status_code == 403
    assert "expected 'approved'" in response.json()["detail"]


def test_gmail_send_success_and_replay_protection(auth_client, test_user):
    """Test successful Gmail send execution with approved approval, followed by replay 403 check."""
    db: Session = next(get_db())
    user_id = test_user.id
    workspace_id = f"ws_user_{user_id}"

    # 1. Create and Approve
    approval = approval_service.create_approval(
        db=db,
        user_id=user_id,
        workspace_id=workspace_id,
        data=ApprovalCreate(
            action_type="gmail.send",
            title="Approved test email",
            payload={"to": "test@example.com", "subject": "Approved Subject", "body": "Approved Body"},
        ),
    )
    approval_service.approve(db, approval.id, user_id, workspace_id)

    # 2. Execute Gmail send with approval_id
    payload = {
        "to": "test@example.com",
        "subject": "Approved Subject",
        "body": "Approved Body",
        "approval_id": approval.id,
    }
    response = auth_client.post("/api/v1/connectors/google/gmail/send", json=payload)
    # The point of this assertion is that *authorization* succeeded. What happens
    # downstream depends on whether Google is reachable and connected: 200 when
    # it is, 409 when the test user has no Google grant, 502 when the connector
    # has one but cannot reach Google. Neither 401 nor 403 is acceptable —
    # those would mean the approved record was not honoured.
    assert response.status_code not in (401, 403), (
        f"Execution authorization failed unexpectedly: {response.json()}"
    )
    assert response.status_code in (200, 409, 502)

    # 3. Replay attempt MUST return 403 Forbidden
    replay_response = auth_client.post("/api/v1/connectors/google/gmail/send", json=payload)
    assert replay_response.status_code == 403
    assert "completed" in replay_response.json()["detail"].lower() or "consumed" in replay_response.json()["detail"].lower() or "failed" in replay_response.json()["detail"].lower()


def test_p7_supervisor_creates_and_pauses_for_approval(test_user):
    """Verify P7 AMOF Supervisor pauses execution as WAITING_FOR_APPROVAL when side-effect is encountered."""
    db: Session = next(get_db())
    context = SupervisorContext(
        question="Send an email to Rahul telling him that the meeting is postponed to Friday.",
        owner_id=str(test_user.id),
        execution_mode="auto",
    )

    response = amof_supervisor.run(db=db, context=context)

    assert response.status == "WAITING_FOR_APPROVAL"
    assert response.approval_id is not None
    assert "requires Human-in-the-Loop approval" in response.answer

    # Verify created approval in database
    approval = approval_service.get_approval(
        db, response.approval_id, test_user.id, f"ws_user_{test_user.id}"
    )
    assert approval.status == "pending"
    assert approval.action_type in ("gmail.send", "text_generation")


def test_p7_supervisor_refuses_to_file_approval_for_unresolvable_owner():
    """
    M17 regression: a non-numeric owner_id must not file the approval against user 1.

    The supervisor used to do `int(owner_id) if owner_id.isdigit() else 1`, so a
    run owned by a non-numeric identifier created a real, approvable gmail.send
    approval belonging to user 1, in user 1's workspace. The run must fail loudly
    instead, and leave no approval behind.
    """
    db: Session = next(get_db())

    approvals_for_user_1_before = (
        db.query(Approval).filter(Approval.user_id == 1).count()
    )

    context = SupervisorContext(
        question="Send an email to Rahul telling him that the meeting is postponed to Friday.",
        owner_id="user_p7_test_owner",
        execution_mode="auto",
    )

    with pytest.raises(ValueError) as exc_info:
        amof_supervisor.run(db=db, context=context)

    assert "not a users.id" in str(exc_info.value)

    # The critical assertion: nothing was filed against the wrong user.
    approvals_for_user_1_after = (
        db.query(Approval).filter(Approval.user_id == 1).count()
    )
    assert approvals_for_user_1_after == approvals_for_user_1_before
