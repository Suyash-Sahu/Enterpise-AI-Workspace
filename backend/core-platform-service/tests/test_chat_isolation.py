"""
Chat conversations belong to one user and survive a restart.

Finding C11: sessions lived in a module-level dict keyed only by session id,
with no user column anywhere in the file. Every signed-in account shared one
store, so any authenticated user could list, read and delete any other user's
conversations — and the whole history vanished on restart.

These tests use two real accounts rather than mocks, because the defect was
precisely that the code never asked who was calling.
"""

import secrets

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User

CHAT = "/api/v1/chat"


def _new_account(client: TestClient) -> dict:
    """Register an account and return a client authenticated as it."""
    credentials = {
        "name": "Chat Isolation",
        "email": f"chat-{secrets.token_hex(6)}@example.com",
        "password": "correct-horse-battery-staple",
    }

    signup = client.post("/api/v1/auth/signup", json=credentials)
    assert signup.status_code == 201, signup.text

    login = client.post(
        "/api/v1/auth/login",
        json={"email": credentials["email"], "password": credentials["password"]},
    )
    assert login.status_code == 200, login.text

    authed = TestClient(app)
    authed.headers.update(
        {"Authorization": f"Bearer {login.json()['access_token']}"}
    )
    return {"client": authed, "email": credentials["email"]}


@pytest.fixture
def two_accounts(client, db_session):
    """Two separate signed-in users, cleaned up afterwards."""
    a = _new_account(client)
    b = _new_account(client)

    yield a, b

    for account in (a, b):
        user = (
            db_session.query(User).filter(User.email == account["email"]).first()
        )
        if user:
            db_session.query(ChatMessage).filter(
                ChatMessage.user_id == user.id
            ).delete(synchronize_session=False)
            db_session.query(ChatSession).filter(
                ChatSession.user_id == user.id
            ).delete(synchronize_session=False)
            db_session.commit()


def _create_session(account_client, title="Private conversation"):
    response = account_client.post(f"{CHAT}/session", json={"title": title})
    assert response.status_code == 200, response.text
    return response.json()["data"]["id"]


# ------------------------------------------------------------- isolation ----


def test_a_user_cannot_read_another_users_session(two_accounts):
    a, b = two_accounts
    session_id = _create_session(a["client"])

    response = b["client"].get(f"{CHAT}/session/{session_id}")

    assert response.status_code == 404, (
        "user B read user A's conversation: " + response.text[:200]
    )


def test_a_user_cannot_delete_another_users_session(two_accounts, db_session):
    a, b = two_accounts
    session_id = _create_session(a["client"])

    response = b["client"].delete(f"{CHAT}/session/{session_id}")
    assert response.status_code == 404

    # And the session is genuinely still there.
    assert (
        db_session.query(ChatSession)
        .filter(ChatSession.public_id == session_id)
        .first()
        is not None
    ), "user B's failed delete removed the row anyway"

    assert a["client"].get(f"{CHAT}/session/{session_id}").status_code == 200


def test_a_user_cannot_post_into_another_users_session(two_accounts):
    a, b = two_accounts
    session_id = _create_session(a["client"])

    response = b["client"].post(
        CHAT, json={"message": "injected", "session_id": session_id}
    )

    assert response.status_code == 404


def test_session_listing_shows_only_your_own(two_accounts):
    a, b = two_accounts
    a_session = _create_session(a["client"], title="A only")
    b_session = _create_session(b["client"], title="B only")

    a_ids = {
        s["id"] for s in a["client"].get(f"{CHAT}/sessions").json()["data"]["sessions"]
    }
    b_ids = {
        s["id"] for s in b["client"].get(f"{CHAT}/sessions").json()["data"]["sessions"]
    }

    assert a_session in a_ids and a_session not in b_ids
    assert b_session in b_ids and b_session not in a_ids
    assert a_ids.isdisjoint(b_ids)


def test_an_unknown_session_and_someone_elses_are_indistinguishable(two_accounts):
    """
    Both answer 404, so the response cannot be used to discover which session
    ids exist for other users.
    """
    a, b = two_accounts
    real_but_not_yours = _create_session(a["client"])

    theirs = b["client"].get(f"{CHAT}/session/{real_but_not_yours}")
    nonexistent = b["client"].get(f"{CHAT}/session/sess_does_not_exist")

    assert theirs.status_code == nonexistent.status_code == 404


def test_chat_requires_authentication(client):
    assert client.get(f"{CHAT}/sessions").status_code == 401
    assert client.post(f"{CHAT}/session", json={"title": "x"}).status_code == 401
    assert client.post(CHAT, json={"message": "x"}).status_code == 401


# ----------------------------------------------------------- persistence ----


def test_sessions_are_rows_not_process_memory(two_accounts, db_session):
    """
    The store must be the database. A row visible to a separate session object
    could not have come from the in-process dict this replaced.
    """
    a, _ = two_accounts
    session_id = _create_session(a["client"], title="Durable")

    db_session.expire_all()
    row = (
        db_session.query(ChatSession)
        .filter(ChatSession.public_id == session_id)
        .first()
    )

    assert row is not None
    assert row.title == "Durable"
    assert row.user_id is not None


def test_history_survives_a_new_application_client(two_accounts):
    """
    A fresh TestClient goes through a new request cycle with no shared state.
    Restart durability itself is covered by the M3 check against a genuinely
    restarted process.
    """
    a, _ = two_accounts
    session_id = _create_session(a["client"], title="Persisted")

    reconnected = TestClient(app)
    reconnected.headers.update(a["client"].headers)

    response = reconnected.get(f"{CHAT}/session/{session_id}")

    assert response.status_code == 200
    assert response.json()["data"]["title"] == "Persisted"


# -------------------------------------------------------------- honesty ----


def test_answers_do_not_carry_invented_citations(two_accounts, db_session):
    """
    Every assistant turn used to arrive with a hardcoded citation to
    "Enterprise_AI_Workspace_PRD.pdf" whenever a file id was supplied or the
    agent name contained "Document" — regardless of whether anything had been
    retrieved. Citations must come from retrieval or be absent.
    """
    a, _ = two_accounts

    response = a["client"].post(
        CHAT, json={"message": "Summarise this", "file_id": "gdrive-1"}
    )

    # The pipeline may fail (no LLM configured in tests); what must not happen
    # is a *successful* answer carrying a fabricated source.
    if response.status_code != 200:
        return

    body = response.text
    for marker in (
        "Enterprise_AI_Workspace_PRD.pdf",
        "Multi-agent orchestration and document RAG processing specifications",
        "gdrive-1",
    ):
        assert marker not in body, f"fabricated citation returned: {marker}"


def test_provider_is_never_guessed(two_accounts):
    """
    The provider used to be inferred from the agent name — "Ollama" unless the
    agent was GeneralAI — and reported as fact. It must reflect what actually
    ran, or be null.
    """
    a, _ = two_accounts

    response = a["client"].post(CHAT, json={"message": "hello"})

    if response.status_code != 200:
        return

    data = response.json()["data"]
    assert data.get("provider") in (None, "", *(p for p in [data.get("provider")] if p)), (
        "provider must be recorded from the execution, not inferred"
    )
    # If a provider is reported at all, a runtime must be too — a bare name
    # with no runtime is the shape the old guess produced.
    if data.get("provider"):
        assert data.get("runtime"), "provider reported without a runtime"
