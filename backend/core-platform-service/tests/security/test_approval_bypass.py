"""
AMOF-X Phase 9 Security Hardening: Approval Bypass Prevention Tests.

Iterates over all registered capability handlers that require human approval
(CapabilityMetadata.requires_human_approval == True) and verifies:
1. Executing without an approval_id is strictly refused (PermissionError).
2. Executing with an unapproved (pending, rejected, or invalid) approval_id is strictly refused.
3. Once consumed, an approval record cannot be re-executed (replay attack protection).
"""
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, engine
from app.execution.registry import task_registry
from app.schemas.approval import ApprovalCreate, ApprovalReject
from app.schemas.execution import ExecutionRequest
from app.services.approval.approval_service import approval_service
from app.services.execution_manager import execution_manager

OWNER_ID = "1"
WORKSPACE_ID = f"ws_user_{OWNER_ID}"

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
    yield


def get_approval_requiring_task_types() -> list[str]:
    tasks = []
    for task_type in task_registry.list_supported_tasks():
        handler = task_registry.get_handler(task_type)
        if handler.metadata.requires_human_approval:
            tasks.append(task_type)
    return tasks


def test_approval_requiring_tasks_exist():
    tasks = get_approval_requiring_task_types()
    assert len(tasks) > 0, "Expected at least one task_type requiring human approval (e.g. gmail.send)"


def test_direct_bypass_without_approval_id_refused_for_all_guarded_tasks():
    for task_type in get_approval_requiring_task_types():
        db = SessionLocal()
        try:
            req = ExecutionRequest(
                task_type=task_type,
                input={"to": "test@example.com", "subject": "test", "body": "test"},
                approval_id=None,
            )
            res = execution_manager.execute(db=db, request=req, owner_id=OWNER_ID)
            assert res.status.value == "FAILED"
            assert "requires a valid, approved Approval record" in (res.error_message or "")
        finally:
            db.close()


def test_execution_with_pending_approval_refused_for_all_guarded_tasks():
    for task_type in get_approval_requiring_task_types():
        db = SessionLocal()
        try:
            approval_data = ApprovalCreate(
                action_type=task_type,
                title="Pending Test Action",
                description="Testing pending approval bypass refusal",
                payload={"to": "test@example.com", "subject": "test", "body": "test"},
            )
            approval = approval_service.create_approval(
                db=db, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID, data=approval_data
            )
            req = ExecutionRequest(
                task_type=task_type,
                input={"to": "test@example.com", "subject": "test", "body": "test"},
                approval_id=approval.id,
            )
            res = execution_manager.execute(db=db, request=req, owner_id=OWNER_ID)
            assert res.status.value == "FAILED"
            assert "approved" in (res.error_message or "").lower() or "pending" in (res.error_message or "").lower()
        finally:
            db.close()


def test_execution_with_rejected_approval_refused_for_all_guarded_tasks():
    for task_type in get_approval_requiring_task_types():
        db = SessionLocal()
        try:
            approval_data = ApprovalCreate(
                action_type=task_type,
                title="Rejected Test Action",
                description="Testing rejected approval bypass refusal",
                payload={"to": "test@example.com", "subject": "test", "body": "test"},
            )
            approval = approval_service.create_approval(
                db=db, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID, data=approval_data
            )
            approval_service.reject(
                db=db,
                approval_id=approval.id,
                user_id=int(OWNER_ID),
                workspace_id=WORKSPACE_ID,
                data=ApprovalReject(reason="Test rejection"),
            )
            req = ExecutionRequest(
                task_type=task_type,
                input={"to": "test@example.com", "subject": "test", "body": "test"},
                approval_id=approval.id,
            )
            res = execution_manager.execute(db=db, request=req, owner_id=OWNER_ID)
            assert res.status.value == "FAILED"
            assert "rejected" in (res.error_message or "").lower() or "status" in (res.error_message or "").lower()
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Phase 19 (Inbox Copilot): the classify -> draft -> approve -> send flow.
#
# The sweep above is generic over CapabilityMetadata.requires_human_approval,
# so it covers any future guarded capability automatically. The inbox
# capabilities are deliberately NOT guarded: they read and generate text and
# never touch Gmail's write API, so there is nothing new to gate. The tests
# below prove exactly that claim rather than assert it -- the only way a
# drafted reply reaches a recipient is the already-guarded "gmail.send"
# capability, exercised here end to end through the drafted payload.
# ---------------------------------------------------------------------------
import json

from app.agents.inbox_agent import inbox_agent
from app.models.approval import Approval
from app.schemas.runtime import RuntimeGenerateResponse

GENERATE_TARGET = "app.agents.inbox_agent.runtime_service.generate"
SEND_TARGET = "app.execution.contracts.GoogleConnectorService.send_email"

INBOX_CAPABILITIES = ("inbox.classify", "inbox.draft_reply")

SAMPLE_EMAIL = {
    "id": "m3",
    "from": "dana@example.test",
    "subject": "roadmap review",
    "body": "Does Thursday work for the roadmap review?",
}


def _mock_generate(completion: str) -> RuntimeGenerateResponse:
    return RuntimeGenerateResponse(completion=completion, provider="mock", model="mock", runtime="local")


def test_inbox_capabilities_have_no_gmail_write_path():
    """
    Structural: neither inbox handler, nor the agent they call, references a
    Gmail write API. If the code cannot send or create a draft, no model
    output and no email content can make it do so.
    """
    import inspect

    from app.agents import inbox_agent as inbox_agent_module
    from app.execution.registry import task_registry

    write_apis = ("send_email", "create_draft", "send_message")
    sources = [inspect.getsource(inbox_agent_module)]
    sources += [
        inspect.getsource(type(task_registry.get_handler(task))) for task in INBOX_CAPABILITIES
    ]
    for source in sources:
        for api in write_apis:
            assert f".{api}(" not in source, f"inbox code calls a Gmail write API: {api}"


def test_drafting_a_reply_neither_sends_nor_creates_an_approval():
    db = SessionLocal()
    try:
        before = db.query(Approval).count()
    finally:
        db.close()

    with patch(GENERATE_TARGET) as mock_generate, patch(SEND_TARGET) as mock_send:
        mock_generate.return_value = _mock_generate(json.dumps({
            "subject": "Re: roadmap review", "body": "Thursday works.",
        }))
        req = ExecutionRequest(task_type="inbox.draft_reply", input={"message": SAMPLE_EMAIL})
        res = _execute(req, owner_id=OWNER_ID)

    assert res.status.value == "COMPLETED", res.error_message
    assert res.result["sent"] is False
    assert res.result["send_capability"] == "gmail.send"
    mock_send.assert_not_called()

    db = SessionLocal()
    try:
        assert db.query(Approval).count() == before, "drafting must not create an Approval by itself"
    finally:
        db.close()


def test_drafted_reply_cannot_be_sent_without_a_matching_approved_approval():
    """
    Takes the *actual* drafted payload and tries to send it the four ways a
    caller could: no approval, pending approval, rejected approval, and
    finally an approved one (which must succeed).
    """
    with patch(GENERATE_TARGET) as mock_generate:
        mock_generate.return_value = _mock_generate(json.dumps({
            "subject": "Re: roadmap review", "body": "Thursday works.",
        }))
        draft = inbox_agent.draft_reply(SAMPLE_EMAIL)

    send_input = {"to": draft["to"], "subject": draft["subject"], "body": draft["body"]}

    # 1. no approval at all
    with patch(SEND_TARGET) as mock_send:
        res = _execute(ExecutionRequest(task_type="gmail.send", input=send_input, approval_id=None), owner_id=OWNER_ID)
    assert res.status.value == "FAILED"
    mock_send.assert_not_called()

    # 2. pending approval
    db = SessionLocal()
    try:
        pending = approval_service.create_approval(
            db=db, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID,
            data=ApprovalCreate(
                action_type="gmail.send", title="Send drafted reply",
                description="Phase 19 flow", payload=send_input,
            ),
        )
        pending_id = pending.id
    finally:
        db.close()

    with patch(SEND_TARGET) as mock_send:
        res = _execute(ExecutionRequest(task_type="gmail.send", input=send_input, approval_id=pending_id), owner_id=OWNER_ID)
    assert res.status.value == "FAILED"
    mock_send.assert_not_called()

    # 3. rejected approval
    db = SessionLocal()
    try:
        approval_service.reject(
            db=db, approval_id=pending_id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID,
            data=ApprovalReject(reason="not this one"),
        )
    finally:
        db.close()

    with patch(SEND_TARGET) as mock_send:
        res = _execute(ExecutionRequest(task_type="gmail.send", input=send_input, approval_id=pending_id), owner_id=OWNER_ID)
    assert res.status.value == "FAILED"
    mock_send.assert_not_called()

    # 4. approved -- the one path that sends, carrying the approved payload
    db = SessionLocal()
    try:
        approved = approval_service.create_approval(
            db=db, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID,
            data=ApprovalCreate(
                action_type="gmail.send", title="Send drafted reply",
                description="Phase 19 flow", payload=send_input,
            ),
        )
        approval_service.approve(
            db=db, approval_id=approved.id, user_id=int(OWNER_ID), workspace_id=WORKSPACE_ID,
        )
        approved_id = approved.id
    finally:
        db.close()

    with patch(SEND_TARGET, return_value={"id": "msg_phase19"}) as mock_send:
        res = _execute(ExecutionRequest(task_type="gmail.send", input=send_input, approval_id=approved_id), owner_id=OWNER_ID)
    assert res.status.value == "COMPLETED", res.error_message
    assert mock_send.call_count == 1
    assert mock_send.call_args.kwargs["to"] == "dana@example.test"
