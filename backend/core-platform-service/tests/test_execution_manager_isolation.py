"""
M17c — /api/v1/execution-manager/* is scoped to the authenticated caller.

Every route in that file hardcoded owner_id = "1", so GET /history handed
user 1's executions to whoever asked. Executions store input_json and
result_json: prompts, generated SQL, retrieved document content. The service
layer filtered on owner_id correctly the whole time; the API never told it who
was asking.

These tests are two-sided on purpose. Asserting only that user B is refused
would also pass on a route that refuses everyone, so each case pairs the denial
with user A still being served.
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.execution import Execution
from app.models.user import User

EM = "/api/v1/execution-manager"


@pytest.fixture
def user_b_client(client, tokens):
    """A second, genuinely different authenticated account."""
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {tokens['access_token']}"})
    return c


@pytest.fixture
def user_b(db_session, registered_user):
    return (
        db_session.query(User)
        .filter(User.email == registered_user["email"])
        .first()
    )


@pytest.fixture
def user_a_execution(db_session, test_user):
    """An execution belonging to user A, carrying recognisable payload data."""
    record = Execution(
        id=f"exec_{uuid.uuid4().hex[:12]}",
        owner_id=str(test_user.id),
        task_type="text_generation",
        execution_mode="auto",
        status="COMPLETED",
        input_json='{"prompt": "SECRET-PROMPT-user-a-confidential"}',
        result_json='{"generated_text": "SECRET-RESULT-user-a-confidential"}',
    )
    db_session.add(record)
    db_session.commit()

    yield record

    db_session.query(Execution).filter(Execution.id == record.id).delete()
    db_session.commit()


def test_history_does_not_leak_another_users_executions(
    auth_client, user_b_client, user_a_execution
):
    """User B must not see user A's execution in their history."""
    b_history = user_b_client.get(f"{EM}/history")
    assert b_history.status_code == 200

    body = b_history.text
    assert user_a_execution.id not in body
    assert "SECRET-PROMPT-user-a-confidential" not in body
    assert "SECRET-RESULT-user-a-confidential" not in body

    # The other half: the route is not simply returning nothing to everyone.
    a_history = auth_client.get(f"{EM}/history")
    assert a_history.status_code == 200
    assert user_a_execution.id in a_history.text


def test_status_of_another_users_execution_is_not_found(
    auth_client, user_b_client, user_a_execution
):
    """Reading user A's execution as user B is a 404, not someone else's data."""
    b_status = user_b_client.get(f"{EM}/status/{user_a_execution.id}")
    assert b_status.status_code == 404
    assert "SECRET-PROMPT-user-a-confidential" not in b_status.text

    # And user A can still read their own, so the 404 means "not yours",
    # not "this route is broken".
    a_status = auth_client.get(f"{EM}/status/{user_a_execution.id}")
    assert a_status.status_code == 200
    assert a_status.json()["data"]["execution_id"] == user_a_execution.id


def test_cancel_of_another_users_execution_is_refused(
    db_session, user_b_client, test_user
):
    """Cancelling across tenants must fail, and must not change the record."""
    record = Execution(
        id=f"exec_{uuid.uuid4().hex[:12]}",
        owner_id=str(test_user.id),
        task_type="text_generation",
        execution_mode="auto",
        status="RUNNING",
    )
    db_session.add(record)
    db_session.commit()

    try:
        resp = user_b_client.post(f"{EM}/cancel/{record.id}")
        assert resp.status_code == 400

        db_session.refresh(record)
        assert record.status == "RUNNING", "another user cancelled this execution"
    finally:
        db_session.query(Execution).filter(Execution.id == record.id).delete()
        db_session.commit()


def test_execute_files_the_execution_against_the_caller(
    db_session, user_b_client, user_b
):
    """
    A submitted task belongs to whoever submitted it.

    Asserted on the persisted row rather than the run's outcome: the executor
    writes the record before dispatching, so this holds whether or not a model
    runtime is reachable.
    """
    resp = user_b_client.post(
        f"{EM}/execute",
        json={"task_type": "text_generation", "input": {"prompt": "hello"}},
    )
    assert resp.status_code == 200

    execution_id = resp.json()["data"]["execution_id"]
    record = (
        db_session.query(Execution).filter(Execution.id == execution_id).first()
    )
    assert record is not None
    assert record.owner_id == str(user_b.id), (
        "execution was filed against the wrong user"
    )


def test_execution_routes_reject_anonymous_callers(client, user_a_execution):
    """No route in this file may answer without a session."""
    assert client.get(f"{EM}/history").status_code == 401
    assert client.get(f"{EM}/status/{user_a_execution.id}").status_code == 401
    assert client.post(f"{EM}/cancel/{user_a_execution.id}").status_code == 401
    assert client.post(
        f"{EM}/execute",
        json={"task_type": "text_generation", "input": {"prompt": "hi"}},
    ).status_code == 401


def test_history_does_not_leak_user_one_executions(db_session, user_b_client, user_b):
    """
    The leak, stated directly.

    The old code looked every caller's history up under owner "1", so whatever
    user 1 had run was returned to everyone. The tests above would not have
    caught that on their own: they use a fixture user who is not user 1, whose
    rows were invisible to all callers rather than visible to the wrong one.
    """
    assert user_b.id != 1, "fixture precondition: user B must not be user 1"

    record = Execution(
        id=f"exec_{uuid.uuid4().hex[:12]}",
        owner_id="1",
        task_type="text_generation",
        execution_mode="auto",
        status="COMPLETED",
        input_json='{"prompt": "USER-ONE-PRIVATE-PROMPT"}',
        result_json='{"generated_text": "USER-ONE-PRIVATE-RESULT"}',
    )
    db_session.add(record)
    db_session.commit()

    try:
        history = user_b_client.get(f"{EM}/history")
        assert history.status_code == 200
        assert record.id not in history.text
        assert "USER-ONE-PRIVATE-PROMPT" not in history.text
        assert "USER-ONE-PRIVATE-RESULT" not in history.text

        status = user_b_client.get(f"{EM}/status/{record.id}")
        assert status.status_code == 404
    finally:
        db_session.query(Execution).filter(Execution.id == record.id).delete()
        db_session.commit()
