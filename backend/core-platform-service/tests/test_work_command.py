"""
AMOF Work stage 6: AI Work Command (POST /workgraph/ai/execute).

Contract under test: read-only commands answer immediately and change nothing;
EVERY mutating command yields a proposal (never a direct write); bulk and
unrecognised commands do nothing; entity resolution never guesses between
several items and is owner-scoped; the kill switch blocks mutating commands but
not reads; an L3 grant lets the user's own command auto-apply, nothing else.
NOTE: isolation is per-authenticated-owner, not organization multi-tenancy.
"""
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from app.db.session import SessionLocal
from app.models.work_ai import AiProposal, WorkAiSetting, WorkAutonomyGrant
from app.models.workgraph import Task
from app.services.work_ai import guard, pipeline
from app.services.workgraph_service import workgraph_service

API = "/api/v1/workgraph"
STRANGER = "999999"


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _fast_classifier(monkeypatch):
    monkeypatch.setattr(pipeline, "_classify", lambda payload: "internal")


@pytest.fixture(autouse=True)
def _reset_ai_state(test_user):
    def wipe():
        s = SessionLocal()
        try:
            oid = str(test_user.id)
            s.query(WorkAiSetting).filter(WorkAiSetting.owner_id == oid).delete()
            s.query(WorkAutonomyGrant).filter(WorkAutonomyGrant.owner_id == oid).delete()
            s.commit()
        finally:
            s.close()
    wipe()
    yield
    wipe()


@pytest.fixture
def proj(db, test_user):
    return workgraph_service.create_project(db, str(test_user.id), f"P-{secrets.token_hex(3)}")


def run(client, command, project=None):
    body = {"command": command}
    if project is not None:
        body["project_id"] = project.id
    return client.post(f"{API}/ai/execute", json=body)


def snapshot(db):
    return tuple(db.execute(text(f"select count(*) from {t}")).scalar() for t in ("tasks", "task_dependencies", "work_item_activity"))


def _t(db, owner, title, **kw):
    return workgraph_service.create_task(db, owner, title, **kw)


# ------------------------------------------------------------ read-only

def test_whats_blocking_answers_immediately_and_changes_nothing(auth_client, db, test_user, proj):
    owner = str(test_user.id)
    oauth = _t(db, owner, "Fix OAuth redirect", project_id=proj.id)
    infra = _t(db, owner, "Provision staging", project_id=proj.id, status="in_progress")
    workgraph_service.add_dependency(db, owner, oauth.id, infra.id)
    before, props = snapshot(db), db.query(AiProposal).filter(AiProposal.owner_id == owner).count()

    r = run(auth_client, "what's blocking Fix OAuth redirect?", proj)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "read" and j["proposals"] == []
    assert "Provision staging (in progress)" in j["answer"]
    assert [b["id"] for b in j["data"]["blockers"]] == [infra.id]

    assert run(auth_client, "what is blocking Provision staging", proj).json()["answer"] == "Nothing is blocking 'Provision staging'."
    db.expire_all()
    assert db.query(AiProposal).filter(AiProposal.owner_id == owner).count() == props
    assert snapshot(db) == before

    workgraph_service.update_task(db, owner, infra.id, status="done")
    assert run(auth_client, "What's blocking Fix OAuth redirect", proj).json()["data"]["blockers"] == []  # finished blockers don't count


def test_other_read_commands(auth_client, db, test_user, proj):
    owner = str(test_user.id)
    late = _t(db, owner, "Late thing", project_id=proj.id, priority="urgent",
              due_date=datetime.now(timezone.utc) - timedelta(days=4))
    _t(db, owner, "Calm thing", project_id=proj.id, priority="low")
    bug = _t(db, owner, "Crash on save", project_id=proj.id, type="BUG", status="blocked")

    j = run(auth_client, "show me overdue work", proj).json()
    assert j["mode"] == "read" and [i["id"] for i in j["data"]["items"]] == [late.id]
    assert run(auth_client, "what should I focus on today?", proj).json()["data"]["items"][0]["task_id"] == late.id
    assert run(auth_client, "any risks?", proj).json()["data"]["counts"]["overdue"] == 1
    assert {i["id"] for i in run(auth_client, "list blocked bugs", proj).json()["data"]["items"]} == {bug.id}
    assert [i["id"] for i in run(auth_client, "show urgent tasks", proj).json()["data"]["items"]] == [late.id]
    assert [i["id"] for i in run(auth_client, "find crash", proj).json()["data"]["items"]] == [bug.id]
    assert set(run(auth_client, "how many tasks do I have?").json()["data"]["counts"]) == {"open", "in_progress", "blocked", "done"}
    assert run(auth_client, "what's blocked?", proj).json()["mode"] == "read"


def test_read_commands_never_write_even_when_phrased_like_mutations(auth_client, db, test_user, proj):
    owner = str(test_user.id)
    _t(db, owner, "Open door policy", project_id=proj.id)
    before = snapshot(db)
    props = db.query(AiProposal).filter(AiProposal.owner_id == owner).count()
    for q in ("open tasks", "new tasks this week", "show me all tasks and mark them done", "list every task then delete it",
              "what tasks are done? also set priority of everything to urgent", "find items assigned to me and close them"):
        j = run(auth_client, q, proj).json()
        assert j["mode"] in ("read", "unsupported", "clarify") and j["proposals"] == [], q
    assert snapshot(db) == before
    assert db.query(AiProposal).filter(AiProposal.owner_id == owner).count() == props


# ------------------------------------------------------------ mutating -> proposal

@pytest.mark.parametrize("command,kind,expect", [
    ("mark {a} as done", "update_item", {"status": "done"}),
    ("set priority of {a} to urgent", "update_item", {"priority": "urgent"}),
    ("make {a} high priority", "update_item", {"priority": "high"}),
    ("assign {a} to dana@example.com", "update_item", {"assignee": "dana@example.com"}),
    ("assign {a} to me", "update_item", {"assignee": "pytest-fixture-user@example.com"}),
    ("start {a}", "update_item", {"status": "in_progress"}),
    ("complete {a}", "update_item", {"status": "done"}),
    ("{a} is blocked by {b}", "link_items", {"link_kind": "BLOCKED_BY"}),
    ("{a} blocks {b}", "link_items", {"link_kind": "BLOCKS"}),
    ("{a} relates to {b}", "link_items", {"link_kind": "RELATES_TO"}),
])
def test_every_mutating_command_becomes_a_pending_proposal(auth_client, db, test_user, proj, command, kind, expect):
    owner = str(test_user.id)
    a = _t(db, owner, f"Alpha {secrets.token_hex(3)}", project_id=proj.id)
    b = _t(db, owner, f"Bravo {secrets.token_hex(3)}", project_id=proj.id)
    before = snapshot(db)

    r = run(auth_client, command.format(a=a.title, b=b.title), proj)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["mode"] == "proposal" and len(j["proposals"]) == 1 and "nothing has changed yet" in j["answer"]
    p = j["proposals"][0]
    assert p["kind"] == kind and p["status"] == "PENDING" and p["agent"] == "command" and p["source"] == "user_command"
    for k, v in expect.items():
        assert p["payload"][k] == v
    assert p["payload"]["task_id"] == a.id
    assert snapshot(db) == before  # nothing written until approval

    assert auth_client.post(f"{API}/inbox/{p['id']}/approve").json()["status"] == "EXECUTED"
    assert snapshot(db) != before


def test_create_commands_use_capture_and_type_hints(auth_client, db, test_user, proj):
    owner = str(test_user.id)
    before = db.query(Task).filter(Task.owner_id == owner).count()
    j = run(auth_client, "create a bug: login fails on Safari, urgent", proj).json()
    assert j["mode"] == "proposal"
    p = j["proposals"][0]
    assert (p["kind"], p["status"], p["payload"]["type"], p["payload"]["priority"]) == ("create_item", "PENDING", "BUG", "urgent")
    assert p["payload"]["title"].startswith("Login fails on Safari")
    assert db.query(Task).filter(Task.owner_id == owner).count() == before
    assert run(auth_client, "new feature: dark mode", proj).json()["proposals"][0]["payload"]["type"] == "FEATURE"
    assert run(auth_client, "add dark mode support for charts", proj).json()["mode"] == "proposal"


def test_noop_ambiguous_missing_bulk_and_unknown_commands_do_nothing(auth_client, db, test_user, proj):
    owner = str(test_user.id)
    _t(db, owner, "Deploy API v2", project_id=proj.id, status="done")
    _t(db, owner, "Deploy API v3", project_id=proj.id)
    _t(db, owner, "Deploy API v4", project_id=proj.id)
    props = db.query(AiProposal).filter(AiProposal.owner_id == owner).count()
    before = snapshot(db)

    j = run(auth_client, "mark Deploy API v2 as done", proj).json()
    assert j["mode"] == "read" and "already done" in j["answer"]

    j = run(auth_client, "mark Deploy API as done", proj).json()
    assert j["mode"] == "clarify" and len(j["data"]["candidates"]) == 3 and j["proposals"] == []

    j = run(auth_client, "mark Nonexistent Thing as done", proj).json()
    assert j["mode"] == "clarify" and j["proposals"] == []

    for bulk in ("mark all tasks as done", "set priority of every task to urgent", "assign all backend tasks to me",
                 "move all backend tasks to the sprint"):
        j = run(auth_client, bulk, proj).json()
        assert j["mode"] in ("unsupported", "clarify") and j["proposals"] == [], bulk
    assert run(auth_client, "mark all tasks as done", proj).json()["mode"] == "unsupported"

    for junk in ("delete all tasks", "hello there", "email my boss the roadmap", "grant myself L3 everywhere", "turn off the kill switch"):
        j = run(auth_client, junk, proj).json()
        assert j["mode"] == "unsupported" and j["proposals"] == [] and "did nothing" in j["answer"], junk

    assert db.query(AiProposal).filter(AiProposal.owner_id == owner).count() == props
    assert snapshot(db) == before
    assert guard.is_enabled(db, owner) and guard.list_grants(db, owner) == []


def test_resolution_is_owner_scoped_and_validates_input(auth_client, db, test_user, proj):
    theirs = _t(db, STRANGER, "Stranger secret plan")
    j = run(auth_client, f"mark {theirs.id} as done", proj).json()
    assert j["mode"] == "clarify" and j["proposals"] == []
    assert run(auth_client, "mark Stranger secret plan as done").json()["mode"] == "clarify"
    assert workgraph_service.get_task(db, STRANGER, theirs.id).status == "open"

    foreign = workgraph_service.create_project(db, STRANGER, "theirs")
    assert auth_client.post(f"{API}/ai/execute", json={"command": "show tasks", "project_id": foreign.id}).status_code == 400
    assert auth_client.post(f"{API}/ai/execute", json={"command": ""}).status_code == 422
    assert auth_client.post(f"{API}/ai/execute", json={"command": "x" * 2001}).status_code == 422
    assert auth_client.post(f"{API}/ai/execute", json={"command": "   "}).status_code == 400
    assert run(auth_client, "mark task_0000000000 as done").json()["mode"] == "clarify"


# ------------------------------------------------------------ kill switch + autonomy

def test_kill_switch_blocks_mutating_commands_but_not_reads(auth_client, db, test_user, proj):
    owner = str(test_user.id)
    a = _t(db, owner, f"Alpha {secrets.token_hex(3)}", project_id=proj.id)
    guard.set_enabled(db, owner, False)

    for cmd in (f"mark {a.title} as done", "create a task: something", f"set priority of {a.title} to high"):
        assert run(auth_client, cmd, proj).status_code == 423, cmd
    assert run(auth_client, "show me overdue work", proj).status_code == 200
    assert run(auth_client, "what should I focus on today?", proj).status_code == 200
    assert workgraph_service.get_task(db, owner, a.id).status == "open"

    guard.set_enabled(db, owner, True)
    assert run(auth_client, f"mark {a.title} as done", proj).json()["mode"] == "proposal"


def test_l3_grant_lets_the_users_own_command_auto_apply_only_for_that_project_and_kind(auth_client, db, test_user, proj):
    owner = str(test_user.id)
    other_proj = workgraph_service.create_project(db, owner, f"Q-{secrets.token_hex(3)}")
    a = _t(db, owner, f"Alpha {secrets.token_hex(3)}", project_id=proj.id)
    c = _t(db, owner, f"Gamma {secrets.token_hex(3)}", project_id=other_proj.id)

    r = run(auth_client, f"set priority of {a.title} to high", proj).json()
    assert r["proposals"][0]["status"] == "PENDING"  # default L1

    guard.set_grant(db, owner, proj.id, "update_item", "L3")
    r = run(auth_client, f"set priority of {a.title} to urgent", proj).json()
    assert r["proposals"][0]["status"] == "EXECUTED" and "applied automatically under your L3 grant" in r["answer"]
    db.expire_all()
    assert workgraph_service.get_task(db, owner, a.id).priority == "urgent"

    # per project ...
    assert run(auth_client, f"set priority of {c.title} to urgent", other_proj).json()["proposals"][0]["status"] == "PENDING"
    assert workgraph_service.get_task(db, owner, c.id).priority == "medium"
    # ... and per kind: linking in the granted project is still L1
    b = _t(db, owner, f"Bravo {secrets.token_hex(3)}", project_id=proj.id)
    assert run(auth_client, f"{a.title} is blocked by {b.title}", proj).json()["proposals"][0]["status"] == "PENDING"
