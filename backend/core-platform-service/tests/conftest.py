"""
Shared test fixtures.

Every API route except the public allowlist requires a bearer token, so tests
that exercise endpoints need an authenticated client rather than a bare
TestClient.
"""

import os
import secrets

import pytest

# Must be set before app.core.config is imported anywhere.
os.environ.setdefault("SECRET_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("INTERNAL_AUTH_SECRET", secrets.token_urlsafe(32))

# Rate limiting is disabled for the suite so functional tests are not throttled
# by each other. The limiter is re-enabled per-test where the limit itself is
# under test — see test_auth.py::test_login_is_rate_limited.
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
os.environ.setdefault("RATE_LIMIT_LOGIN", "3/minute")

from fastapi.testclient import TestClient  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402
from app.db.seed import seed_roles  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.role import Role  # noqa: E402
from app.models.session import Session as UserSession  # noqa: E402
from app.models.user import User  # noqa: E402

TEST_USER_EMAIL = "pytest-fixture-user@example.com"

# Routes reachable without credentials, by design.
PUBLIC_PATHS = {
    "/",
    "/api/v1/health",
    "/api/v1/auth/signup",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
    # The backend now owns Google sign-in end to end. Both legs are
    # necessarily anonymous: the browser arrives with no session, and
    # establishing one is the point.
    "/api/v1/auth/google/login",
    "/api/v1/auth/google/callback",
    "/api/v1/connectors/google/oauth/callback",
    "/api/v1/approvals/health",
    # NOTE: /api/v1/evaluation/health is deliberately NOT here — unlike the
    # other health endpoints it requires authentication.
    "/api/v1/cache/health",
}


@pytest.fixture(autouse=True)
def _isolate_evaluation_artifacts(tmp_path, monkeypatch):
    """
    Test runs must never write into the real evaluation/artifacts/ directory.

    EvaluationRunner.start_run() unconditionally writes run_<id>/ there. Tests
    that drive it with fixture rows (task_001, 120 ms, 150 tokens) left 45 of
    the 50 stored evaluation_results.csv files in that directory as one
    repeated fixture task, indistinguishable from a real run. Redirecting the
    directory per test keeps research artifacts free of fixture data.
    """
    from app.evaluation.runner import EvaluationRunner

    monkeypatch.setattr(EvaluationRunner, "ARTIFACTS_DIR", str(tmp_path / "evaluation_artifacts"))


@pytest.fixture(scope="session")
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session")
def test_user(db_session):
    """A stable user for the whole test session, created once if absent."""
    seed_roles(db_session)

    user = db_session.query(User).filter(User.email == TEST_USER_EMAIL).first()

    if user is None:
        role = db_session.query(Role).filter(Role.name == "user").first()
        user = User(
            name="Pytest Fixture User",
            email=TEST_USER_EMAIL,
            password_hash=hash_password(secrets.token_urlsafe(32)[:64]),
            role_id=role.id,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

    return user


@pytest.fixture(scope="session")
def access_token(test_user):
    token, _, _ = create_access_token(
        {"sub": str(test_user.id), "email": test_user.email, "role": "user"}
    )
    return token


@pytest.fixture(scope="session")
def client():
    """Unauthenticated client — asserts that routes reject anonymous callers."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def _anonymous_client_between_tests(client):
    """
    Start every test with an empty cookie jar.

    The backend sets session cookies on login, and TestClient keeps a cookie
    jar for the life of the (session-scoped) client. Without this, one test
    logging in would leave the shared client authenticated, and every later
    test asserting that a route rejects anonymous callers would quietly pass
    for the wrong reason — or fail, as two of them did.
    """
    client.cookies.clear()
    yield
    client.cookies.clear()


@pytest.fixture(scope="session")
def auth_client(access_token):
    """Client carrying a valid access token for the fixture user."""
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {access_token}"})
    return c


@pytest.fixture
def fresh_credentials():
    """
    A unique, unregistered email/password pair.

    Tests share a real database, so every account-creating test needs its own
    address or the second run collides with the first.
    """
    return {
        "name": "Auth Test User",
        "email": f"authtest-{secrets.token_hex(6)}@example.com",
        "password": "correct-horse-battery-staple",
    }


@pytest.fixture
def registered_user(client, fresh_credentials, db_session):
    """A signed-up account, removed along with its sessions afterwards."""
    resp = client.post("/api/v1/auth/signup", json=fresh_credentials)
    assert resp.status_code == 201, resp.text

    yield fresh_credentials

    user = (
        db_session.query(User)
        .filter(User.email == fresh_credentials["email"])
        .first()
    )
    if user:
        db_session.query(UserSession).filter(
            UserSession.user_id == user.id
        ).delete(synchronize_session=False)
        db_session.delete(user)
        db_session.commit()


@pytest.fixture
def tokens(client, registered_user):
    """
    A freshly issued access/refresh pair for a throwaway account.

    The login that mints them also sets session cookies. They are dropped
    here so the pair is only usable where a test passes it explicitly —
    ambient credentials would make "this route rejects anonymous callers"
    unprovable.
    """
    resp = client.post(
        "/api/v1/auth/login",
        json={
            "email": registered_user["email"],
            "password": registered_user["password"],
        },
    )
    assert resp.status_code == 200, resp.text

    client.cookies.clear()

    return resp.json()
