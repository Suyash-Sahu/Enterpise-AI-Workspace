from app.main import app


def test_connect_route_requires_authentication(client):
    """The Google connect flow must not be startable by an anonymous caller."""
    response = client.get(
        "/api/v1/connectors/google/login", follow_redirects=False
    )
    assert response.status_code == 401


def test_connect_route_returns_authorization_url(auth_client):
    """
    Authenticated callers get the authorization URL as JSON.

    This used to be a 307 redirect, which could not carry a bearer token and so
    could not be authenticated at all.
    """
    response = auth_client.get("/api/v1/connectors/google/login")
    assert response.status_code == 200

    url = response.json()["data"]["authorization_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "response_type=code" in url
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert "state=" in url


def test_google_callback_missing_code_redirects_with_error(client):
    response = client.get(
        "/api/v1/connectors/google/oauth/callback?state=whatever",
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert "error=missing_parameters" in response.headers["location"]


def test_google_callback_missing_state_redirects_with_error(client):
    response = client.get(
        "/api/v1/connectors/google/oauth/callback?code=mock_code",
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert "error=missing_parameters" in response.headers["location"]


def test_google_callback_invalid_state_redirects_with_error(client):
    response = client.get(
        "/api/v1/connectors/google/oauth/callback"
        "?code=mock_code&state=nonexistent_state_12345",
        follow_redirects=False,
    )
    assert response.status_code == 307
    assert "error=invalid_state" in response.headers["location"]


def test_google_status_requires_authentication(client):
    assert client.get("/api/v1/connectors/google/status").status_code == 401


def test_google_status_returns_safe_schema(auth_client):
    response = auth_client.get("/api/v1/connectors/google/status")
    assert response.status_code == 200

    data = response.json()["data"]
    assert "connected" in data

    # Credentials must never appear in a status payload.
    assert "access_token" not in data
    assert "refresh_token" not in data
    assert "client_secret" not in data


def test_openapi_route_registry_consistency():
    paths = list(app.openapi()["paths"].keys())

    duplicate_paths = [p for p in paths if "/api/v1/api/v1" in p]
    assert not duplicate_paths, f"Found duplicate route prefixes: {duplicate_paths}"

    assert "/api/v1/connectors/google/login" in paths
    assert "/api/v1/connectors/google/oauth/callback" in paths
    assert "/api/v1/connectors/google/status" in paths

# --------------------------------------------------- OAuth state handling ----
#
# Finding H1: state rows carried no user binding, no expiry and no TTL check,
# so a state minted at any point in the past still validated — and the callback
# wrote the resulting grant to a hardcoded user_id=1 regardless of who
# completed the flow.


def test_oauth_state_is_bound_to_the_user_who_started_the_flow(
    auth_client, test_user, db_session
):
    from app.models.oauth_state import OAuthState

    resp = auth_client.get("/api/v1/connectors/google/login")
    assert resp.status_code == 200

    url = resp.json()["data"]["authorization_url"]
    state = url.split("state=")[1].split("&")[0]

    row = db_session.query(OAuthState).filter(OAuthState.state == state).first()
    assert row is not None
    assert row.user_id == test_user.id, "state must be bound to its originator"
    assert row.expires_at is not None, "state must carry an expiry"

    db_session.delete(row)
    db_session.commit()


def test_oauth_state_is_single_use(client, auth_client, db_session):
    """A replayed callback must find nothing, so a code cannot be redeemed twice."""
    from app.models.oauth_state import OAuthState

    resp = auth_client.get("/api/v1/connectors/google/login")
    state = resp.json()["data"]["authorization_url"].split("state=")[1].split("&")[0]

    assert (
        db_session.query(OAuthState).filter(OAuthState.state == state).first()
        is not None
    )

    # Consume it. The token exchange fails (no real Google), but the row must
    # be gone regardless.
    client.get(
        f"/api/v1/connectors/google/oauth/callback?code=fake&state={state}",
        follow_redirects=False,
    )

    db_session.expire_all()
    assert (
        db_session.query(OAuthState).filter(OAuthState.state == state).first()
        is None
    ), "state row must be consumed on first use"


def test_expired_oauth_state_is_rejected(client, test_user, db_session):
    from datetime import datetime, timedelta, timezone

    from app.models.oauth_state import OAuthState

    stale = OAuthState(
        state="stale-state-value-for-test",
        code_verifier="irrelevant",
        user_id=test_user.id,
        expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )
    db_session.add(stale)
    db_session.commit()

    resp = client.get(
        "/api/v1/connectors/google/oauth/callback"
        "?code=fake&state=stale-state-value-for-test",
        follow_redirects=False,
    )

    assert resp.status_code == 307
    assert "error=invalid_state" in resp.headers["location"]

    db_session.expire_all()
    leftover = (
        db_session.query(OAuthState)
        .filter(OAuthState.state == "stale-state-value-for-test")
        .first()
    )
    if leftover:
        db_session.delete(leftover)
        db_session.commit()


def test_callback_never_returns_upstream_error_detail(client):
    """
    Finding H4: the callback returned Google's raw token-endpoint JSON to the
    caller. Errors are now opaque redirect codes.
    """
    resp = client.get(
        "/api/v1/connectors/google/oauth/callback?code=fake&state=nonexistent",
        follow_redirects=False,
    )

    assert resp.status_code == 307
    location = resp.headers["location"]
    for leak in ("client_secret", "invalid_grant", "access_token"):
        assert leak not in location
