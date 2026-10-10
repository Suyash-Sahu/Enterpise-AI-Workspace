"""
Route-level authorization sweep.

Findings C2 and C3: roughly 53 routes had no auth dependency at all — every
Gmail, Drive, document, chat, RAG and SQL-agent endpoint was reachable
anonymously, and the connector routes acted as a hardcoded user_id=1.

Auth is now applied at router mount time with an explicit public allowlist, so
the useful test is not "is route X protected" but "is the set of public routes
exactly the set we intended". This walks the live OpenAPI schema, so a route
added later is covered without anyone remembering to add a test.
"""

import pytest

from conftest import PUBLIC_PATHS

# Placeholders for path parameters. Values only need to be well-formed enough
# to reach the auth dependency, which runs before the handler.
PATH_PARAM_VALUES = {
    "file_id": "test-file-id",
    "message_id": "test-message-id",
    "thread_id": "test-thread-id",
    "document_id": "test-document-id",
    "approval_id": "1",
    "run_id": "test-run-id",
    "session_id": "test-session-id",
}

METHODS = ("get", "post", "put", "patch", "delete")


def _concrete(path: str) -> str:
    for name, value in PATH_PARAM_VALUES.items():
        path = path.replace("{" + name + "}", value)
    return path


def _all_operations(app):
    for path, operations in sorted(app.openapi()["paths"].items()):
        for method in operations:
            if method in METHODS:
                yield method, path


def test_every_route_is_either_public_by_design_or_authenticated(client):
    """
    No route may be reachable anonymously unless it is on the allowlist.

    A new endpoint that forgets its auth dependency fails here.
    """
    leaked = []

    for method, path in _all_operations(client.app):
        if path in PUBLIC_PATHS:
            continue

        response = client.request(
            method, _concrete(path), json={}, follow_redirects=False
        )

        if response.status_code != 401:
            leaked.append(f"{method.upper()} {path} -> {response.status_code}")

    assert not leaked, "routes reachable without authentication:\n  " + "\n  ".join(
        leaked
    )


def test_public_allowlist_contains_no_unknown_paths(client):
    """
    The allowlist must not drift either: an entry for a route that no longer
    exists would silently stop protecting anything.
    """
    documented = set(client.app.openapi()["paths"]) | {"/"}
    stale = sorted(PUBLIC_PATHS - documented)

    assert not stale, f"allowlist references paths that do not exist: {stale}"


def test_public_routes_are_actually_reachable(client):
    """The allowlisted routes must not require auth by accident."""
    blocked = []

    for method, path in _all_operations(client.app):
        if path not in PUBLIC_PATHS:
            continue

        response = client.request(
            method, _concrete(path), json={}, follow_redirects=False
        )

        # A redirect from the OAuth callback means it ran, i.e. it is public.
        if response.status_code == 401:
            blocked.append(f"{method.upper()} {path}")

    assert not blocked, f"public routes returning 401: {blocked}"


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/connectors/google/gmail/messages",
        "/api/v1/connectors/google/drive/files",
        "/api/v1/connectors/google/status",
        "/api/v1/workspace/dashboard",
        "/api/v1/users/me",
    ],
)
def test_named_high_value_routes_reject_anonymous_callers(client, path):
    """
    Explicit coverage for the endpoints that were most exposed, so a
    regression names the specific route rather than only failing the sweep.
    """
    assert client.get(path).status_code == 401


def test_admin_route_requires_more_than_being_signed_in(auth_client):
    """
    Finding: require_role existed but was never enforced on a mounted route,
    so "authenticated" was the only real check anywhere in the app.
    """
    response = auth_client.get("/api/v1/admin/dashboard")

    # The fixture user holds the 'user' role, not 'admin'.
    assert response.status_code == 403


def test_raw_sql_endpoint_requires_the_admin_role(auth_client):
    """
    Finding H6/C10: /db-agent/sql accepts arbitrary SQL text, so being signed
    in is not sufficient authorization to reach it.
    """
    response = auth_client.post(
        "/api/v1/db-agent/sql",
        json={"sql": "SELECT id FROM users", "limit": 1},
    )

    # 403 either because raw SQL is disabled or because the role is wrong;
    # both are refusals, and neither may be a 200.
    assert response.status_code == 403
