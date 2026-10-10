"""
Rate limiting must bucket callers individually, not collectively.

Regression from the Phase 1 rework. Two changes combined badly:

  * the browser moved from an Authorization header to a session cookie, and
    client_key only ever looked at the header; and
  * every browser request now arrives through the Next proxy, so the peer
    address the API sees is always the proxy's.

Together those meant every signed-in user fell through to the same
`ip:127.0.0.1` bucket. One user refreshing too often exhausted the limit for
everyone — which is exactly what was observed: a wave of 429s on
/auth/refresh keyed to `ip:127.0.0.1`.
"""

from types import SimpleNamespace

from app.core.config import settings
from app.core.rate_limit import client_key
from app.core.security import create_access_token, create_refresh_token


def _request(headers=None, cookies=None, peer="127.0.0.1"):
    """A stand-in carrying only what client_key reads."""
    return SimpleNamespace(
        headers={k.lower(): v for k, v in (headers or {}).items()},
        cookies=cookies or {},
        client=SimpleNamespace(host=peer, port=0),
        scope={"client": (peer, 0), "headers": []},
    )


def _access_token_for(subject: str) -> str:
    token, _, _ = create_access_token({"sub": subject})
    return token


# ------------------------------------------------------------- bucketing ----


def test_cookie_authenticated_callers_bucket_per_user():
    """The defect: cookies were ignored, so these collapsed into one bucket."""
    a = _request(cookies={settings.ACCESS_COOKIE_NAME: _access_token_for("11")})
    b = _request(cookies={settings.ACCESS_COOKIE_NAME: _access_token_for("22")})

    key_a = client_key(a)
    key_b = client_key(b)

    assert key_a == "user:11"
    assert key_b == "user:22"
    assert key_a != key_b, "two signed-in users shared one rate-limit bucket"


def test_bearer_callers_still_bucket_per_user():
    request = _request(headers={"Authorization": f"Bearer {_access_token_for('33')}"})

    assert client_key(request) == "user:33"


def test_the_same_user_over_two_transports_is_one_bucket():
    """
    Cookie and header are the same credential, so they must not grant two
    budgets to one account.
    """
    token = _access_token_for("44")

    by_cookie = client_key(_request(cookies={settings.ACCESS_COOKIE_NAME: token}))
    by_header = client_key(_request(headers={"Authorization": f"Bearer {token}"}))

    assert by_cookie == by_header == "user:44"


def test_refresh_requests_bucket_by_session_not_by_proxy_address():
    """
    /auth/refresh carries no access token by definition — that is the point of
    calling it. Without this, every refresh in the system shared one bucket,
    which is what produced the observed 429 storm.
    """
    refresh_a, _, _ = create_refresh_token({"sub": "55"})
    refresh_b, _, _ = create_refresh_token({"sub": "66"})

    key_a = client_key(_request(cookies={settings.REFRESH_COOKIE_NAME: refresh_a}))
    key_b = client_key(_request(cookies={settings.REFRESH_COOKIE_NAME: refresh_b}))

    assert key_a.startswith("session:")
    assert key_a != key_b, "two sessions shared one refresh budget"


# --------------------------------------------------------- proxied peers ----


def test_forwarded_client_is_honoured_from_the_local_proxy():
    """
    Anonymous traffic still needs distinguishing, and behind the proxy the peer
    is always loopback.
    """
    request = _request(
        headers={"X-Forwarded-For": "203.0.113.7, 127.0.0.1"}, peer="127.0.0.1"
    )

    assert client_key(request) == "ip:203.0.113.7"


def test_forwarded_header_is_ignored_from_an_untrusted_peer():
    """
    Otherwise any caller could claim a fresh bucket per request and opt out of
    rate limiting entirely.
    """
    request = _request(
        headers={"X-Forwarded-For": "203.0.113.7"}, peer="198.51.100.4"
    )

    assert client_key(request) == "ip:198.51.100.4"


def test_anonymous_callers_fall_back_to_the_peer_address():
    assert client_key(_request(peer="198.51.100.9")) == "ip:198.51.100.9"


def test_a_malformed_token_does_not_raise():
    """
    The subject is read without verification, so garbage must degrade to the
    address rather than 500 the request it was meant to be limiting.
    """
    request = _request(cookies={settings.ACCESS_COOKIE_NAME: "not-a-jwt"})

    assert client_key(request).startswith("ip:")
