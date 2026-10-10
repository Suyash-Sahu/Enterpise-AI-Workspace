"""
The connector must report what Google actually returned, or fail.

Every bug covered here failed silently and looked like success:

  * `list_gmail_messages` passed `limit` into the `user_id` parameter, so it
    looked up a Google grant for user 20, raised, and returned a hardcoded
    inbox from the `except` branch. `/gmail/messages` therefore served two
    invented emails to every caller — including callers with no Google account
    connected at all — while `/drive/files` correctly errored. That difference
    is what made the connector look "half working" rather than broken.

  * Five handlers answered failures with fabricated data: an invented mailbox
    profile, invented messages, an invented message body, and empty threads.

  * `WorkspaceService.summary` called `get_dashboard(db)` without `user_id`, so
    `/workspace/summary` raised TypeError and returned 500 on every request.

  * The dashboard returned a fixed payload — 148 Drive files, 12 messages, 4
    unread, and the address `alex.dev@enterprise.ai` — regardless of who was
    signed in or whether Google was connected.

The fixture user has no Google grant, so "no fabricated data" is checkable
without touching the network: any real-looking content in these responses can
only have been invented.
"""

import pytest

from app.connectors.google.exceptions import GoogleNotConnectedError
from app.services.google_connector_service import GoogleConnectorService
from app.services.workspace_service import WorkspaceService

# Strings that only ever appeared in the hardcoded fallbacks.
FABRICATED_MARKERS = (
    "alex.dev@enterprise.ai",
    "msg-101",
    "msg-102",
    "th-101",
    "gdrive-1",
    "Enterprise_AI_Workspace_PRD.pdf",
    "AMOF_Agent_Topology_Architecture.docx",
    "Enterprise AI Message Details",
    "Google Workspace OAuth Status Active",
)


GMAIL_READ_ENDPOINTS = [
    "/api/v1/connectors/google/gmail/messages",
    "/api/v1/connectors/google/gmail/threads",
    "/api/v1/connectors/google/gmail/profile",
    "/api/v1/connectors/google/gmail/message/abc123",
    "/api/v1/connectors/google/gmail/thread/abc123",
    "/api/v1/connectors/google/drive/files",
]


@pytest.mark.parametrize("path", GMAIL_READ_ENDPOINTS)
def test_unconnected_user_gets_an_error_not_invented_data(auth_client, path):
    """
    With no Google grant, every read must fail. It must not succeed with
    plausible-looking content.
    """
    response = auth_client.get(path)

    assert response.status_code == 409, (
        f"{path} returned {response.status_code}; a user with no Google account "
        f"must not receive a success: {response.text[:200]}"
    )

    body = response.text
    for marker in FABRICATED_MARKERS:
        assert marker not in body, f"{path} returned fabricated content: {marker}"


def test_not_connected_is_distinguishable_from_an_upstream_failure(auth_client):
    """
    409 means "connect an account", 502 means "Google refused". Collapsing both
    into 502 left the UI offering a retry for a problem retrying cannot fix.
    """
    response = auth_client.get("/api/v1/connectors/google/gmail/messages")

    assert response.status_code == 409
    assert "connect" in response.json()["detail"].lower()


def test_list_gmail_messages_forwards_the_caller_id_not_the_limit(monkeypatch):
    """
    Regression: the caller's id must reach the token lookup.

    `list_message_details(db, limit)` bound `limit` to `user_id`, so the
    connector fetched a Google grant belonging to whatever number the limit
    happened to be.
    """
    seen = {}

    def recorder(db, user_id, limit=10):
        seen["user_id"] = user_id
        seen["limit"] = limit
        return []

    monkeypatch.setattr(GoogleConnectorService, "list_message_details", recorder)

    GoogleConnectorService.list_gmail_messages(db=None, user_id=4242, limit=7)

    assert seen == {"user_id": 4242, "limit": 7}


def test_list_gmail_threads_forwards_the_caller_id_not_the_limit(monkeypatch):
    """Same positional bug, same fix, on the threads path."""
    seen = {}

    def recorder(db, user_id, limit=20):
        seen["user_id"] = user_id
        seen["limit"] = limit
        return []

    monkeypatch.setattr(GoogleConnectorService, "list_threads", recorder)

    GoogleConnectorService.list_gmail_threads(db=None, user_id=4242, limit=9)

    assert seen == {"user_id": 4242, "limit": 9}


def test_workspace_summary_does_not_error(auth_client):
    """Regression: summary() dropped user_id, so this was a guaranteed 500."""
    response = auth_client.get("/api/v1/workspace/summary")

    assert response.status_code == 200, response.text


def test_dashboard_reports_the_real_account_and_no_invented_counts(
    auth_client, test_user
):
    """
    The dashboard must describe the signed-in user's own workspace. With no
    Google grant that means their address and empty sections — not a stock
    payload that looks identical for everyone.
    """
    response = auth_client.get("/api/v1/workspace/dashboard")
    assert response.status_code == 200, response.text

    data = response.json()["data"]

    assert data["user"]["email"] == test_user.email
    assert data["workspace"]["connected"] is False

    # The old fixed figures.
    assert data["drive"]["count"] == 0
    assert data["drive"]["recent"] == []
    assert data["gmail"]["latest"] == []
    assert data["gmail"]["count"] == 0
    assert data["gmail"]["unread"] == 0

    for marker in FABRICATED_MARKERS:
        assert marker not in response.text


def test_dashboard_does_not_call_google_when_nothing_is_connected(
    auth_client, monkeypatch
):
    """
    A disconnected workspace must not attempt Google calls at all — the
    connection check happens before any network work.
    """

    def explode(*args, **kwargs):
        raise AssertionError("Google was contacted for a disconnected user")

    monkeypatch.setattr(
        "app.services.workspace_service.GmailClient", explode
    )
    monkeypatch.setattr(
        "app.services.workspace_service.GoogleDriveClient", explode
    )

    assert auth_client.get("/api/v1/workspace/dashboard").status_code == 200


def test_missing_grant_raises_the_typed_error(db_session, test_user):
    """
    TokenService signals "not connected" with a type the API layer can map,
    rather than a bare Exception indistinguishable from an upstream fault.
    """
    from app.services.token_service import TokenService

    with pytest.raises(GoogleNotConnectedError):
        TokenService.get_google_token(db_session, user_id=test_user.id)


def test_dashboard_marks_failed_sections_unavailable_rather_than_zero(
    db_session, test_user, monkeypatch
):
    """
    A section that could not be read must say so. Reporting 0 would read as
    "your Drive is empty", which is a different and wrong statement.
    """
    class StubGrant:
        google_email = "connected.account@example.com"

    monkeypatch.setattr(
        "app.services.workspace_service.WorkspaceService._active_grant",
        staticmethod(lambda db, user_id: StubGrant()),
    )
    monkeypatch.setattr(
        "app.services.token_service.TokenService.get_google_token",
        staticmethod(lambda db, user_id: "token-value"),
    )

    class BrokenClient:
        def __init__(self, *args, **kwargs):
            pass

        def __getattr__(self, name):
            def boom(*args, **kwargs):
                raise RuntimeError("Google is down")

            return boom

    monkeypatch.setattr("app.services.workspace_service.GmailClient", BrokenClient)
    monkeypatch.setattr(
        "app.services.workspace_service.GoogleDriveClient", BrokenClient
    )

    data = WorkspaceService.get_dashboard(db=db_session, user_id=test_user.id)

    assert set(data["workspace"]["unavailable"]) == {"drive", "gmail"}
    assert data["drive"]["recent"] == []
    assert data["gmail"]["latest"] == []


# ---------------------------------------------------------------------------
# Transport behaviour
#
# Reading an inbox page costs one list call plus one call per message. Those
# ran sequentially over connections that were opened and thrown away one per
# request, so a 20-message page took ~34s and /gmail/unread failed outright
# with a connection reset. These lock in the three properties that fixed it.
# ---------------------------------------------------------------------------


def test_message_details_are_fetched_concurrently_and_stay_in_order(monkeypatch):
    """
    The fan-out must overlap the round trips, and must not reorder the inbox
    while doing so.
    """
    import time

    from app.connectors.google.gmail import GmailClient
    from app.services.google_connector_service import fetch_message_details

    def slow_detail(self, message_id):
        time.sleep(0.2)
        return {"id": message_id}

    monkeypatch.setattr(GmailClient, "get_message_details", slow_detail)

    messages = [{"id": f"m{i}"} for i in range(8)]

    started = time.monotonic()
    details = fetch_message_details("access-token", messages)
    elapsed = time.monotonic() - started

    assert [d["id"] for d in details] == [m["id"] for m in messages]

    # Sequentially this is 8 x 0.2s = 1.6s. Concurrently it is one batch.
    assert elapsed < 1.0, f"details were fetched sequentially ({elapsed:.2f}s)"


def test_message_details_skips_entries_without_an_id(monkeypatch):
    from app.connectors.google.gmail import GmailClient
    from app.services.google_connector_service import fetch_message_details

    monkeypatch.setattr(
        GmailClient, "get_message_details", lambda self, mid: {"id": mid}
    )

    details = fetch_message_details("access-token", [{"id": "a"}, {}, {"id": "b"}])

    assert [d["id"] for d in details] == ["a", "b"]


def test_gmail_client_reuses_one_connection_and_sets_a_timeout():
    """
    A Session keeps the connection alive across the many calls one page needs,
    and every request carries a timeout so a stalled call cannot hang the
    request thread indefinitely.
    """
    import requests

    from app.connectors.google.gmail import GmailClient

    client = GmailClient("access-token")

    assert isinstance(client._session, requests.Session)
    assert client.TIMEOUT_SECONDS > 0

    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs)

        class Response:
            text = "{}"

            def raise_for_status(self):
                return None

            def json(self):
                return {}

        return Response()

    client._session.request = fake_request
    client.get_profile()

    assert captured["timeout"] == GmailClient.TIMEOUT_SECONDS


def test_retries_never_duplicate_a_sent_email():
    """
    Retrying a send could deliver the same message twice. urllib3's default
    allowed_methods covers idempotent verbs only, so POST — send and draft —
    must not be retried.
    """
    from app.connectors.google.gmail import GmailClient

    allowed = GmailClient._RETRY_POLICY.allowed_methods

    assert "POST" not in allowed
    assert "GET" in allowed
