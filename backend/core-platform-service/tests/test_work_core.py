"""
AMOF Work stage 1: core work management (extends WorkGraph).

Covers owner isolation (per-user tenant boundary), IDOR on every new route,
unauthorized dependency creation, cycle rejection, and the append-only
activity trail. NOTE: AMOF Work isolation is per-authenticated-owner, not
organization multi-tenancy or RBAC.
"""
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.role import Role
from app.models.user import User

API = "/api/v1/workgraph"


@pytest.fixture(scope="module")
def other_client():
    """A second, unrelated authenticated user (the IDOR attacker)."""
    db = SessionLocal()
    try:
        role = db.query(Role).filter(Role.name == "user").first()
        user = User(
            name="Work Other User",
            email=f"work-other-{secrets.token_hex(5)}@example.com",
            password_hash=hash_password(secrets.token_urlsafe(24)),
            role_id=role.id,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token, _, _ = create_access_token({"sub": str(user.id), "email": user.email, "role": "user"})
    finally:
        db.close()
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {token}"})
    return c


def _task(c, **kw):
    r = c.post(f"{API}/tasks", json={"title": kw.pop("title", "t"), **kw})
    assert r.status_code == 201, r.text
    return r.json()


# ---------------------------------------------------------------- provenance

def test_human_task_provenance_and_client_cannot_forge_it(auth_client, test_user):
    r = auth_client.post(f"{API}/tasks", json={
        "title": "forge attempt", "type": "BUG",
        "owner_id": "999999", "created_by": "ai", "created_by_actor": "agent:capture",
        "ai_confidence": 0.99, "source_type": "automation",
    })
    assert r.status_code == 201
    t = r.json()
    assert t["owner_id"] == str(test_user.id)
    assert t["created_by"] == "human"
    assert t["created_by_actor"] == f"user:{test_user.id}"
    assert t["source_type"] == "manual"
    assert t["ai_confidence"] is None
    assert t["type"] == "BUG"


# ---------------------------------------------------------------------- IDOR

def test_other_user_cannot_read_or_touch_owners_items(auth_client, other_client):
    proj = auth_client.post(f"{API}/projects", json={"name": "Private P"}).json()
    task = _task(auth_client, title="Private T", project_id=proj["id"])

    reads = [
        f"/projects/{proj['id']}", f"/projects/{proj['id']}/board", f"/projects/{proj['id']}/stats",
        f"/tasks/{task['id']}", f"/tasks/{task['id']}/activity", f"/tasks/{task['id']}/links",
        f"/tasks/{task['id']}/dependencies",
    ]
    for path in reads:
        assert other_client.get(API + path).status_code == 404, path

    assert other_client.patch(f"{API}/tasks/{task['id']}", json={"status": "done"}).status_code == 404
    assert other_client.patch(f"{API}/projects/{proj['id']}", json={"name": "pwn"}).status_code == 404

    # Not leaked via list/search/dashboard either.
    assert all(t["id"] != task["id"] for t in other_client.get(f"{API}/tasks").json())
    assert all(t["id"] != task["id"] for t in other_client.get(f"{API}/tasks?search=Private").json())
    dash = other_client.get(f"{API}/dashboard").json()
    for key in ("due_today", "overdue", "recently_updated"):
        assert all(t["id"] != task["id"] for t in dash[key])

    # Owner's data is unchanged.
    assert auth_client.get(f"{API}/tasks/{task['id']}").json()["status"] == "open"


def test_cannot_create_item_in_someone_elses_project(auth_client, other_client):
    proj = auth_client.post(f"{API}/projects", json={"name": "Mine"}).json()
    r = other_client.post(f"{API}/tasks", json={"title": "sneak", "project_id": proj["id"]})
    assert r.status_code == 400
    assert all(t["title"] != "sneak" for t in auth_client.get(f"{API}/tasks?project_id={proj['id']}").json())


# ------------------------------------------------------------- dependencies

def test_unauthorized_dependency_creation_is_rejected(auth_client, other_client):
    mine = _task(auth_client, title="mine")
    theirs = _task(other_client, title="theirs")

    # link my task to their task, and vice versa, via the dependency route
    assert auth_client.post(f"{API}/tasks/{mine['id']}/dependencies",
                            json={"depends_on_task_id": theirs["id"]}).status_code == 400
    assert other_client.post(f"{API}/tasks/{theirs['id']}/dependencies",
                             json={"depends_on_task_id": mine["id"]}).status_code == 400
    assert other_client.post(f"{API}/tasks/{mine['id']}/dependencies",
                             json={"depends_on_task_id": theirs['id']}).status_code == 400

    # ...and via depends_on on create (previously unchecked)
    r = auth_client.post(f"{API}/tasks", json={"title": "x", "depends_on": [theirs["id"]]})
    assert r.status_code == 400
    assert auth_client.get(f"{API}/tasks/{mine['id']}/links").json() == {"blocked_by": [], "blocks": [], "relates_to": []}


def test_self_and_circular_dependencies_rejected(auth_client):
    a, b, c = (_task(auth_client, title=n) for n in "abc")
    dep = lambda x, y, **k: auth_client.post(f"{API}/tasks/{x['id']}/dependencies",
                                             json={"depends_on_task_id": y["id"], **k})

    assert dep(a, a).status_code == 400
    assert dep(a, b).status_code == 201          # a blocked by b
    assert dep(b, c).status_code == 201          # b blocked by c
    assert dep(c, a).status_code == 400          # c blocked by a  -> cycle
    assert dep(c, a, kind="BLOCKED_BY").status_code == 400
    assert dep(a, c, kind="BLOCKS").status_code == 400   # a BLOCKS c == c blocked by a -> cycle
    assert dep(c, a, kind="RELATES_TO").status_code == 201  # informational link never cycles


def test_blocks_is_normalised_and_links_are_directional(auth_client):
    a, b = _task(auth_client, title="a"), _task(auth_client, title="b")
    r = auth_client.post(f"{API}/tasks/{a['id']}/dependencies",
                         json={"depends_on_task_id": b["id"], "kind": "BLOCKS"})
    assert r.status_code == 201
    assert auth_client.get(f"{API}/tasks/{a['id']}/links").json()["blocks"] == [b["id"]]
    assert auth_client.get(f"{API}/tasks/{b['id']}/links").json()["blocked_by"] == [a["id"]]
    assert auth_client.get(f"{API}/tasks/{b['id']}").json()["depends_on"] == [a["id"]]


def test_relates_to_is_not_a_blocker(auth_client):
    a, b = _task(auth_client, title="a"), _task(auth_client, title="b")
    auth_client.post(f"{API}/tasks/{a['id']}/dependencies",
                     json={"depends_on_task_id": b["id"], "kind": "RELATES_TO"})
    assert auth_client.get(f"{API}/tasks/{a['id']}").json()["depends_on"] == []
    assert auth_client.get(f"{API}/tasks/{b['id']}/links").json()["relates_to"] == [a["id"]]


# ----------------------------------------------------------------- activity

def test_activity_trail_records_events_and_is_append_only(auth_client, test_user):
    t = _task(auth_client, title="tracked")
    other = _task(auth_client, title="peer")
    auth_client.patch(f"{API}/tasks/{t['id']}", json={"status": "in_progress"})
    auth_client.patch(f"{API}/tasks/{t['id']}", json={"priority": "urgent", "title": "tracked!"})
    auth_client.post(f"{API}/tasks/{t['id']}/dependencies", json={"depends_on_task_id": other["id"]})
    auth_client.delete(f"{API}/tasks/{t['id']}/dependencies/{other['id']}")

    events = auth_client.get(f"{API}/tasks/{t['id']}/activity").json()
    kinds = [e["event_type"] for e in reversed(events)]  # API is newest-first
    assert kinds == ["created", "status_changed", "updated", "dependency_added", "dependency_removed"]
    assert all(e["actor"] == f"user:{test_user.id}" for e in events)
    assert events[-1]["payload"]["source_type"] == "manual"

    # No mutation surface on the trail.
    for method in ("put", "patch", "delete", "post"):
        assert getattr(auth_client, method)(f"{API}/tasks/{t['id']}/activity").status_code == 405


# ---------------------------------------------------------- search / dashboard

def test_filters_search_overdue_my_work(auth_client, test_user):
    past = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    tag = secrets.token_hex(4)
    late = _task(auth_client, title=f"late-{tag}", priority="urgent", due_date=past, assignee=test_user.email)
    done_late = _task(auth_client, title=f"donelate-{tag}", due_date=past, status="done")
    lit = _task(auth_client, title=f"100% literal_{tag}")

    q = lambda s: {t["id"] for t in auth_client.get(f"{API}/tasks?{s}").json()}
    assert late["id"] in q("overdue=true")
    assert done_late["id"] not in q("overdue=true")
    assert late["id"] in q("priority=urgent") and lit["id"] not in q("priority=urgent")
    assert late["id"] in q("assignee=me")
    assert q(f"search=%25 literal_{tag}") == {lit["id"]}   # % and _ are literals, not wildcards
    assert late["id"] in q(f"due_before={datetime.now(timezone.utc).isoformat().replace('+', '%2B')}")


def test_dashboard_and_board_and_stats(auth_client):
    proj = auth_client.post(f"{API}/projects", json={"name": "Board P"}).json()
    for title, st in (("o", "open"), ("p", "in_progress"), ("b", "blocked"), ("d", "done"), ("r", "in_review")):
        _task(auth_client, title=title, status=st, project_id=proj["id"])

    board = auth_client.get(f"{API}/projects/{proj['id']}/board").json()["columns"]
    assert {k: len(v) for k, v in board.items()} == {"open": 1, "in_progress": 2, "blocked": 1, "done": 1}

    stats = auth_client.get(f"{API}/projects/{proj['id']}/stats").json()
    assert stats["total"] == 5 and stats["counts"]["in_progress"] == 2

    dash = auth_client.get(f"{API}/dashboard").json()
    assert set(dash) == {"counts", "due_today", "overdue", "recently_updated"}
    assert dash["counts"]["blocked"] >= 1 and len(dash["recently_updated"]) <= 10


def test_update_task_cannot_reassign_owner_via_service(auth_client, test_user):
    """Service-level guard: only whitelisted fields are mutable."""
    from app.services.workgraph_service import workgraph_service
    t = _task(auth_client, title="own")
    db = SessionLocal()
    try:
        workgraph_service.update_task(db, str(test_user.id), t["id"], created_by="ai", source_type="automation", title="ok")
        row = workgraph_service.get_task(db, str(test_user.id), t["id"])
        assert row is not None and row.source_type == "manual" and row.created_by == "human"
        assert row.title == "ok"
    finally:
        db.close()
