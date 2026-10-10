"""
Authentication and session security.

Every test here maps to a finding from the security audit. Before this file
existed there were no auth tests at all, which is why the largest findings
(unauthenticated routes, refresh tokens usable as access tokens) survived.
"""

import time
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import (
    hash_password,
    needs_rehash,
    verify_password,
    verify_token,
)
from app.models.oauth_state import PURPOSE_CONNECT, PURPOSE_SIGNIN, OAuthState
from app.models.session import Session as UserSession
from app.models.user import User
from app.services.auth_service import login_or_register_google_user
from app.services.oauth_service import save_oauth_state

AUTH = "/api/v1/auth"


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------- signup ----


def test_signup_creates_account(client, fresh_credentials, db_session):
    resp = client.post(f"{AUTH}/signup", json=fresh_credentials)
    assert resp.status_code == 201

    body = resp.json()
    assert body["email"] == fresh_credentials["email"]
    assert "password" not in body and "password_hash" not in body

    user = (
        db_session.query(User)
        .filter(User.email == fresh_credentials["email"])
        .first()
    )
    db_session.delete(user)
    db_session.commit()


def test_signup_rejects_duplicate_email(client, registered_user):
    resp = client.post(f"{AUTH}/signup", json=registered_user)
    assert resp.status_code == 400


@pytest.mark.parametrize(
    "password,reason",
    [
        ("", "empty"),
        ("short", "below minimum length"),
        ("elevenchar", "one under the minimum"),
        ("x" * 100, "over bcrypt 72-byte ceiling"),
    ],
)
def test_signup_enforces_password_policy(
    client, fresh_credentials, password, reason
):
    """Finding H10: password was a bare str with no constraints at all."""
    resp = client.post(
        f"{AUTH}/signup", json={**fresh_credentials, "password": password}
    )
    assert resp.status_code == 422, f"should reject {reason}"


def test_signup_validation_error_does_not_echo_password(
    client, fresh_credentials
):
    """Finding H4: the default validation handler returned the input back."""
    # Short enough to fail validation, distinctive enough to spot if echoed.
    secret = "hunter2"
    resp = client.post(
        f"{AUTH}/signup", json={**fresh_credentials, "password": secret}
    )
    assert resp.status_code == 422
    assert secret not in resp.text


# ----------------------------------------------------------------- login ----


def test_login_returns_token_pair(client, registered_user):
    resp = client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 200

    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"] and body["refresh_token"]
    assert body["access_token"] != body["refresh_token"]


def test_login_rejects_wrong_password(client, registered_user):
    resp = client.post(
        f"{AUTH}/login",
        json={"email": registered_user["email"], "password": "not-the-password"},
    )
    assert resp.status_code == 401


def test_login_does_not_reveal_whether_the_account_exists(
    client, registered_user
):
    """Login must not distinguish "no such user" from "wrong password"."""
    wrong_password = client.post(
        f"{AUTH}/login",
        json={"email": registered_user["email"], "password": "not-the-password"},
    )
    no_such_user = client.post(
        f"{AUTH}/login",
        json={
            "email": f"absent-{uuid.uuid4().hex}@example.com",
            "password": "not-the-password",
        },
    )

    assert wrong_password.status_code == no_such_user.status_code == 401
    assert wrong_password.json()["detail"] == no_such_user.json()["detail"]


def test_login_timing_does_not_leak_account_existence(client, registered_user):
    """
    A missing account must still cost a password verification, or response
    time distinguishes the two cases regardless of the message.
    """

    def elapsed(email):
        start = time.perf_counter()
        client.post(
            f"{AUTH}/login", json={"email": email, "password": "not-the-password"}
        )
        return time.perf_counter() - start

    existing = min(elapsed(registered_user["email"]) for _ in range(3))
    missing = min(
        elapsed(f"absent-{uuid.uuid4().hex}@example.com") for _ in range(3)
    )

    # Generous bound: this catches "returns instantly", not micro-differences.
    assert missing > existing * 0.25, (
        f"missing-account path was much faster ({missing:.4f}s vs "
        f"{existing:.4f}s), which leaks whether an account exists"
    )


def test_login_is_rate_limited(client, registered_user):
    """Finding H3: unlimited attempts allowed credential stuffing."""
    limiter = client.app.state.limiter
    limiter.reset()
    limiter.enabled = True

    try:
        codes = [
            client.post(
                f"{AUTH}/login",
                json={
                    "email": registered_user["email"],
                    "password": "not-the-password",
                },
            ).status_code
            for _ in range(6)
        ]
    finally:
        limiter.enabled = False
        limiter.reset()

    assert 429 in codes, f"expected throttling, got {codes}"
    assert codes[0] == 401, "first attempt should be evaluated, not discarded"


# ------------------------------------------------------- token semantics ----


def test_access_token_authenticates(client, tokens):
    resp = client.get("/api/v1/users/me", headers=_bearer(tokens["access_token"]))
    assert resp.status_code == 200


def test_refresh_token_is_not_accepted_as_an_access_token(client, tokens):
    """
    Finding C4: both tokens were signed with the same key and carried no type
    claim, so a refresh token was a valid 7-day bearer token and the short
    access expiry meant nothing.
    """
    resp = client.get(
        "/api/v1/users/me", headers=_bearer(tokens["refresh_token"])
    )
    assert resp.status_code == 401


def test_access_token_is_not_accepted_as_a_refresh_token(client, tokens):
    resp = client.post(
        f"{AUTH}/refresh", json={"refresh_token": tokens["access_token"]}
    )
    assert resp.status_code == 401


def test_tokens_carry_type_and_identity_claims(tokens):
    payload = verify_token(tokens["access_token"], expected_type="access")
    assert payload is not None
    for claim in ("sub", "jti", "typ", "iat", "exp"):
        assert claim in payload
    assert payload["typ"] == "access"


@pytest.mark.parametrize(
    "token",
    ["", "garbage", "a.b.c", "Bearer", "x" * 500],
    ids=["empty", "garbage", "three-parts", "word", "long"],
)
def test_malformed_tokens_are_rejected_with_401(client, token):
    """Finding H12: unguarded int(payload['sub']) turned these into 500s."""
    resp = client.get("/api/v1/users/me", headers=_bearer(token))
    assert resp.status_code == 401


def test_expired_access_token_is_rejected(client, test_user):
    expired = jwt.encode(
        {
            "sub": str(test_user.id),
            "typ": "access",
            "jti": str(uuid.uuid4()),
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    assert client.get("/api/v1/users/me", headers=_bearer(expired)).status_code == 401


def test_token_signed_with_the_wrong_key_is_rejected(client, test_user):
    forged = jwt.encode(
        {
            "sub": str(test_user.id),
            "typ": "access",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        "an-attacker-chosen-signing-key-that-is-long-enough",
        algorithm=settings.ALGORITHM,
    )
    assert client.get("/api/v1/users/me", headers=_bearer(forged)).status_code == 401


def test_token_without_subject_is_rejected(client):
    no_sub = jwt.encode(
        {
            "typ": "access",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    assert client.get("/api/v1/users/me", headers=_bearer(no_sub)).status_code == 401


def test_token_for_a_nonexistent_user_is_rejected(client):
    ghost = jwt.encode(
        {
            "sub": "99999999",
            "typ": "access",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    assert client.get("/api/v1/users/me", headers=_bearer(ghost)).status_code == 401


# --------------------------------------------------------------- refresh ----


def test_refresh_rotates_the_token(client, tokens):
    resp = client.post(
        f"{AUTH}/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 200

    rotated = resp.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]
    assert (
        client.get(
            "/api/v1/users/me", headers=_bearer(rotated["access_token"])
        ).status_code
        == 200
    )


def test_replaying_a_consumed_refresh_token_fails(client, tokens):
    first = client.post(
        f"{AUTH}/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert first.status_code == 200

    replay = client.post(
        f"{AUTH}/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert replay.status_code == 401


def test_reuse_revokes_the_whole_token_family(client, tokens):
    """
    Presenting a consumed token means it leaked, so every descendant of that
    login is revoked, not just the replayed one.
    """
    rotated = client.post(
        f"{AUTH}/refresh", json={"refresh_token": tokens["refresh_token"]}
    ).json()

    # Replay the consumed token: detected as reuse.
    client.post(f"{AUTH}/refresh", json={"refresh_token": tokens["refresh_token"]})

    # The legitimate rotated token is collateral damage, by design.
    assert (
        client.post(
            f"{AUTH}/refresh", json={"refresh_token": rotated["refresh_token"]}
        ).status_code
        == 401
    )


def test_refresh_token_is_stored_only_as_a_hash(tokens, db_session):
    """The raw refresh token must never be recoverable from the database."""
    stored = [row.token_hash for row in db_session.query(UserSession).all()]
    assert tokens["refresh_token"] not in stored


def test_unknown_refresh_token_is_rejected(client):
    resp = client.post(f"{AUTH}/refresh", json={"refresh_token": "not-a-token"})
    assert resp.status_code == 401


# ---------------------------------------------------------------- logout ----


def test_logout_revokes_the_refresh_token_server_side(client, tokens):
    """
    Finding C8: there was no logout endpoint at all, so a captured refresh
    token stayed valid for its full 7 days.
    """
    resp = client.post(
        f"{AUTH}/logout",
        json={"refresh_token": tokens["refresh_token"]},
        headers=_bearer(tokens["access_token"]),
    )
    assert resp.status_code == 204

    assert (
        client.post(
            f"{AUTH}/refresh", json={"refresh_token": tokens["refresh_token"]}
        ).status_code
        == 401
    )


def test_logout_requires_authentication(client, tokens):
    resp = client.post(
        f"{AUTH}/logout", json={"refresh_token": tokens["refresh_token"]}
    )
    assert resp.status_code == 401


# ------------------------------------------------------ google sign-in ----
#
# The Next.js server used to verify the Google identity and trade it for a
# token pair over a shared-secret endpoint, which meant two systems believed
# they established sessions. The backend now owns the whole round trip, so
# these cover the state machine rather than the retired exchange.


def test_google_signin_start_redirects_to_google_with_pkce(client):
    resp = client.get(f"{AUTH}/google/login", follow_redirects=False)

    assert resp.status_code in (302, 307)

    location = resp.headers["location"]
    query = parse_qs(urlparse(location).query)

    assert location.startswith("https://accounts.google.com/")
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0]
    assert query["state"][0]

    # Signing in must not ask for mail or files.
    scopes = set(query["scope"][0].split())
    assert scopes == {"openid", "email", "profile"}


def test_google_signin_state_is_recorded_without_a_user(client, db_session):
    resp = client.get(f"{AUTH}/google/login", follow_redirects=False)
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]

    row = db_session.query(OAuthState).filter(OAuthState.state == state).first()

    assert row is not None
    assert row.purpose == PURPOSE_SIGNIN
    # Who is signing in is not known until Google answers.
    assert row.user_id is None

    db_session.delete(row)
    db_session.commit()


def test_google_signin_callback_rejects_an_unknown_state(client):
    resp = client.get(
        f"{AUTH}/google/callback?code=abc&state=never-issued",
        follow_redirects=False,
    )

    assert resp.status_code in (302, 307)
    assert "error=invalid_state" in resp.headers["location"]


def test_google_signin_callback_requires_a_code(client):
    resp = client.get(f"{AUTH}/google/callback?state=x", follow_redirects=False)

    assert resp.status_code in (302, 307)
    assert "error=missing_code" in resp.headers["location"]


def test_a_signin_state_cannot_be_redeemed_at_the_connector_callback(
    client, db_session
):
    """
    Purpose is enforced, not decorative: a state minted for signing in must
    not be usable to attach a Google grant to an account.
    """
    resp = client.get(f"{AUTH}/google/login", follow_redirects=False)
    state = parse_qs(urlparse(resp.headers["location"]).query)["state"][0]

    connector_callback = "/api/v1/connectors/google/oauth/callback"
    result = client.get(
        f"{connector_callback}?code=abc&state={state}", follow_redirects=False
    )

    assert result.status_code in (302, 307)
    assert "connected=false" in result.headers["location"]

    # And the state is burned rather than left for a second attempt.
    assert (
        db_session.query(OAuthState).filter(OAuthState.state == state).first()
        is None
    )


def test_a_connect_state_at_the_signin_callback_never_creates_a_session(
    client, db_session
):
    """
    The sign-in callback also completes Gmail/Drive consent, so that only one
    redirect URI has to be registered with Google. That routing must not
    become a privilege escalation: a state minted for CONNECT is a request to
    attach a grant to an already-authenticated user, and must never mint a
    session for whoever happens to be holding it.
    """
    state = "connect-state-" + uuid.uuid4().hex
    save_oauth_state(
        db=db_session,
        state=state,
        verifier="v" * 64,
        user_id=None,
        purpose=PURPOSE_CONNECT,
    )
    db_session.commit()

    resp = client.get(
        f"{AUTH}/google/callback?code=abc&state={state}", follow_redirects=False
    )

    assert resp.status_code in (302, 307)

    # It is handled as a connector failure (the token exchange cannot succeed
    # against a fake code), never as a sign-in.
    assert "/integrations" in resp.headers["location"]
    assert "connected=false" in resp.headers["location"]

    # The decisive part: no session was issued.
    assert settings.ACCESS_COOKIE_NAME not in resp.cookies
    assert settings.REFRESH_COOKIE_NAME not in resp.cookies

    # And the state is single-use regardless of which callback consumed it.
    assert (
        db_session.query(OAuthState).filter(OAuthState.state == state).first()
        is None
    )


def test_google_signin_is_the_only_way_into_a_google_account(client, db_session):
    """
    A Google-created account has no usable password, so it cannot be reached
    through the password login.
    """
    email = f"g-{uuid.uuid4().hex}@example.com"
    tokens = login_or_register_google_user(db_session, email=email, name="G")

    assert tokens["access_token"]

    user = db_session.query(User).filter(User.email == email).first()
    assert user is not None

    assert (
        client.post(
            f"{AUTH}/login", json={"email": email, "password": ""}
        ).status_code
        in (401, 422)
    )

    db_session.query(UserSession).filter(
        UserSession.user_id == user.id
    ).delete(synchronize_session=False)
    db_session.delete(user)
    db_session.commit()


# ------------------------------------------------------- password hashing ----


def test_passwords_are_hashed_with_argon2():
    hashed = hash_password("correct-horse-battery-staple")
    assert hashed.startswith("$argon2")
    assert verify_password("correct-horse-battery-staple", hashed)
    assert not verify_password("wrong", hashed)


def test_legacy_bcrypt_hashes_verify_and_are_flagged_for_upgrade():
    """Finding H11: migrating off passlib must not lock out existing accounts."""
    import bcrypt

    legacy = bcrypt.hashpw(
        b"legacy-password-123", bcrypt.gensalt(rounds=4)
    ).decode()

    assert verify_password("legacy-password-123", legacy)
    assert not verify_password("wrong", legacy)
    assert needs_rehash(legacy), "bcrypt hashes should upgrade on next login"
    assert not needs_rehash(hash_password("x" * 20))


@pytest.mark.parametrize("bad", ["", "not-a-hash", "$2b$broken", None])
def test_verify_password_never_raises_on_a_malformed_hash(bad):
    assert verify_password("anything", bad) is False


# --------------------------------------------------------- session cookies ----
#
# The Next.js app used to mint these itself from tokens fetched over a
# shared-secret channel, so two systems believed they owned the session. The
# backend is now the only issuer, and these pin the properties that make a
# cookie session safe to rely on.


def _set_cookie_headers(response):
    return response.headers.get_list("set-cookie")


def _cookie_named(response, name):
    for header in _set_cookie_headers(response):
        if header.startswith(f"{name}="):
            return header
    return None


def test_login_sets_httponly_session_cookies(client, registered_user):
    resp = client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 200

    access = _cookie_named(resp, settings.ACCESS_COOKIE_NAME)
    refresh = _cookie_named(resp, settings.REFRESH_COOKIE_NAME)

    assert access is not None, "login must establish the session itself"
    assert refresh is not None

    # Script must not be able to read either token.
    assert "HttpOnly" in access
    assert "HttpOnly" in refresh

    # SameSite=lax is what keeps CSRF a non-issue for this API: the cookie is
    # withheld from cross-site POSTs, iframes and subresource requests, and
    # sent only on top-level GET navigations.
    #
    # It must NOT be strict. Google sign-in ends with Google redirecting the
    # browser back to this app, and a Strict cookie is withheld across a
    # cross-site-initiated redirect chain — the session would be stored and
    # then never sent, so the route guard would bounce the user to /login and
    # sign-in would appear to fail. This assertion pins the value that keeps
    # that flow working.
    assert "SameSite=lax" in access.replace("samesite", "SameSite")
    assert "SameSite=lax" in refresh.replace("samesite", "SameSite")

    # The refresh token is scoped to the auth routes; nothing else needs it.
    assert "Path=/api/v1/auth" in refresh
    assert "Path=/" in access


def test_the_cookie_alone_authenticates_a_request(client, registered_user):
    """No Authorization header anywhere — the browser's path must work."""
    client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    resp = client.get("/api/v1/users/me")

    assert resp.status_code == 200
    assert resp.json()["email"] == registered_user["email"]


def test_refresh_rotates_the_cookie(client, registered_user):
    client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    before = client.cookies.get(settings.REFRESH_COOKIE_NAME)

    resp = client.post(f"{AUTH}/refresh")

    assert resp.status_code == 200
    assert _cookie_named(resp, settings.REFRESH_COOKIE_NAME) is not None

    after = client.cookies.get(settings.REFRESH_COOKIE_NAME)
    assert after and after != before, "rotation must replace the stored cookie"


def test_refresh_works_from_the_cookie_with_no_body(client, registered_user):
    """The browser has no way to put the token in a body — it is httpOnly."""
    client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    assert client.post(f"{AUTH}/refresh").status_code == 200


def test_refresh_without_any_token_is_rejected(client):
    assert client.post(f"{AUTH}/refresh").status_code == 401


def test_logout_clears_both_cookies(client, registered_user):
    client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    resp = client.post(f"{AUTH}/logout")
    assert resp.status_code == 204

    # Both cookies must be expired, and with the same paths they were set on
    # or the browser keeps the originals.
    headers = " ".join(_set_cookie_headers(resp))
    assert settings.ACCESS_COOKIE_NAME in headers
    assert settings.REFRESH_COOKIE_NAME in headers

    # And the session is genuinely over, not just cleared client-side.
    assert client.get("/api/v1/users/me").status_code == 401


def test_a_failed_refresh_clears_the_dead_cookies(client, registered_user):
    """
    A revoked session must not leave cookies behind that fail on every
    subsequent request.
    """
    client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    client.post(f"{AUTH}/logout")

    # Put a known-dead refresh token back and try to use it.
    resp = client.post(f"{AUTH}/refresh", json={"refresh_token": "not-a-token"})

    assert resp.status_code == 401
    assert _set_cookie_headers(resp), "dead cookies must be cleared"


# ------------------------------------------------------------------- csrf ----


def test_cross_origin_state_change_with_cookies_is_rejected(client, registered_user):
    """
    SameSite=strict already stops the browser sending these, but a second
    layer costs nothing and covers a loosened policy or an untrusted subdomain.
    """
    client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    resp = client.post(
        f"{AUTH}/logout",
        headers={"Origin": "https://attacker.example"},
    )

    assert resp.status_code == 403


def test_same_origin_state_change_is_allowed(client, registered_user):
    client.post(
        f"{AUTH}/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )

    resp = client.post(
        f"{AUTH}/logout",
        headers={"Origin": settings.FRONTEND_URL},
    )

    assert resp.status_code == 204


def test_bearer_callers_are_not_subject_to_the_origin_check(auth_client):
    """
    A token holder has no ambient authority to abuse, so the origin check
    must not break scripts and API clients.
    """
    resp = auth_client.get(
        "/api/v1/users/me", headers={"Origin": "https://somewhere.example"}
    )

    assert resp.status_code == 200
