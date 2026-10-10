"""
Project 8 — Approval & HITL Unit and Security Test Suite
Tests CRUD operations, state transitions, edit preservation, atomic claims,
replay protection, expiration handling, and multi-tenant isolation.
"""

from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.dependencies import get_db
from app.models.approval import Approval
from app.models.approval_event import ApprovalEvent
from app.schemas.approval import ApprovalCreate, ApprovalEdit, ApprovalReject
from app.services.approval.approval_policy import approval_policy
from app.services.approval.approval_service import approval_service

client = TestClient(app)


def test_approval_policy_rules():
    """Verify action side-effect policy classifications."""
    assert approval_policy.requires_approval("gmail.send") is True
    assert approval_policy.requires_approval("calendar.create") is True
    assert approval_policy.requires_approval("webhook.post") is True
    assert approval_policy.requires_approval("document.search") is False
    assert approval_policy.requires_approval("rag.query") is False
    assert approval_policy.requires_approval("database.query") is False
    assert approval_policy.get_risk_level("gmail.send") == "high"


def test_approval_health_endpoint():
    """Verify GET /api/v1/approvals/health telemetry."""
    response = client.get("/api/v1/approvals/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["approvals_enabled"] is True


def test_approval_creation_and_lifecycle():
    """Test approval creation, edit preservation, approve transition, and audit trail."""
    db: Session = next(get_db())
    user_id = 1
    workspace_id = f"ws_user_{user_id}"

    # 1. Create approval
    create_dto = ApprovalCreate(
        action_type="gmail.send",
        title="Send meeting postponement email",
        description="Send email to Rahul regarding meeting update",
        payload={"to": "rahul@example.com", "subject": "Meeting Update", "body": "Meeting moved to Friday"},
        risk_level="high",
        execution_id="exec_test_001",
    )
    approval = approval_service.create_approval(db, user_id, workspace_id, create_dto)
    assert approval.id is not None
    assert approval.status == "pending"
    assert approval.edited_payload is None

    # 2. Edit payload (Status MUST remain pending)
    edit_dto = ApprovalEdit(
        edited_payload={"to": "rahul@example.com", "subject": "Meeting Update Final", "body": "Meeting is now on Friday at 3 PM."}
    )
    edited_app = approval_service.edit(db, approval.id, user_id, workspace_id, edit_dto)
    assert edited_app.status == "pending"
    assert edited_app.edited_payload["subject"] == "Meeting Update Final"

    # 3. List pending approvals
    items, total = approval_service.list_pending(db, user_id, workspace_id)
    assert total >= 1
    found = any(item.id == approval.id for item in items)
    assert found is True

    # 4. Approve
    approved_app = approval_service.approve(db, approval.id, user_id, workspace_id)
    assert approved_app.status == "approved"
    assert approved_app.approved_at is not None

    # 5. Audit timeline
    events = approval_service.get_approval_events(db, approval.id, user_id, workspace_id)
    assert len(events) >= 3
    event_types = [e.event_type for e in events]
    assert "CREATED" in event_types
    assert "EDITED" in event_types
    assert "APPROVED" in event_types


def test_approval_rejection_flow():
    """Test rejection transition: PENDING -> REJECTED."""
    db: Session = next(get_db())
    user_id = 1
    workspace_id = f"ws_user_{user_id}"

    create_dto = ApprovalCreate(
        action_type="gmail.send",
        title="Send marketing blast",
        payload={"to": "all@example.com", "subject": "Promo", "body": "Discount code"},
    )
    approval = approval_service.create_approval(db, user_id, workspace_id, create_dto)

    rejected_app = approval_service.reject(
        db, approval.id, user_id, workspace_id, ApprovalReject(reason="Do not send unsolicited email")
    )
    assert rejected_app.status == "rejected"
    assert rejected_app.rejected_at is not None


def test_approval_atomic_claim_and_replay_protection():
    """Test atomic claim (approved -> executing -> completed) and replay prevention."""
    db: Session = next(get_db())
    user_id = 1
    workspace_id = f"ws_user_{user_id}"

    create_dto = ApprovalCreate(
        action_type="gmail.send",
        title="Send status email",
        payload={"to": "dev@example.com", "subject": "Build OK", "body": "Build passed"},
    )
    approval = approval_service.create_approval(db, user_id, workspace_id, create_dto)
    approval_service.approve(db, approval.id, user_id, workspace_id)

    # First claim succeeds and resolves effective payload
    effective_payload = approval_service.begin_execution(
        db, approval.id, user_id, workspace_id, "gmail.send"
    )
    assert effective_payload["subject"] == "Build OK"

    # Verify status is executing
    claimed_app = db.query(Approval).filter(Approval.id == approval.id).first()
    assert claimed_app.status == "executing"

    # Replay attempt while executing MUST fail with 403
    with pytest.raises(Exception) as exc_info:
        approval_service.begin_execution(db, approval.id, user_id, workspace_id, "gmail.send")
    assert "403" in str(exc_info.value) or "consumed" in str(exc_info.value).lower()

    # Complete execution
    completed_app = approval_service.complete_execution(db, approval.id, user_id)
    assert completed_app.status == "completed"

    # Replay attempt after completed MUST fail with 403
    with pytest.raises(Exception) as exc_info:
        approval_service.begin_execution(db, approval.id, user_id, workspace_id, "gmail.send")
    assert "403" in str(exc_info.value) or "status is 'completed'" in str(exc_info.value)


def test_approval_expiration():
    """Test expired record handling."""
    db: Session = next(get_db())
    user_id = 1
    workspace_id = f"ws_user_{user_id}"

    now = datetime.now(timezone.utc)
    past = now - timedelta(minutes=10)

    expired_app = Approval(
        user_id=user_id,
        workspace_id=workspace_id,
        action_type="gmail.send",
        status="pending",
        title="Expired test",
        payload={"test": True},
        expires_at=past,
        created_at=past,
        updated_at=past,
    )
    db.add(expired_app)
    db.commit()
    db.refresh(expired_app)

    with pytest.raises(Exception) as exc_info:
        approval_service.approve(db, expired_app.id, user_id, workspace_id)
    assert "expired" in str(exc_info.value).lower()


def test_tenant_isolation():
    """Test user B cannot view or approve user A's approval."""
    db: Session = next(get_db())
    user_a = 1
    workspace_a = "ws_user_1"
    user_b = 2
    workspace_b = "ws_user_2"

    create_dto = ApprovalCreate(
        action_type="gmail.send",
        title="User A Private Approval",
        payload={"secret": "data"},
    )
    approval = approval_service.create_approval(db, user_a, workspace_a, create_dto)

    with pytest.raises(Exception) as exc_info:
        approval_service.get_approval(db, approval.id, user_b, workspace_b)
    assert "not found" in str(exc_info.value).lower() or "404" in str(exc_info.value)
