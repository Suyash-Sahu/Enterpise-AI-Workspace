"""
AMOF Work stage 4: AI proposal -> approval/autonomy pipeline, kill switch, AI Inbox.

Security properties proven here (against the real DB and the real executor):
  * agent output never mutates WorkGraph until an Approval is claimed
  * no approval / pending / rejected / forged-proposal => execution fails
  * replay of an approved proposal executes at most once
  * IDOR across users on proposals and on referenced projects/items
  * approved payload tampering (generic approvals edit endpoint) is re-validated
  * kill switch: blocks new proposals, cancels pending, blocks already-approved
  * L3 is per-(project, kind), audited, and refused at the execution layer
    even when a bad grant row exists
NOTE: isolation is per-authenticated-owner, not organization multi-tenancy.
"""
import secrets

import pytest
from fastapi.testclient import TestClient

from app.core.security import create_access_token, hash_password
from app.db.session import SessionLocal
from app.main import app
from app.models.approval import Approval
from app.models.approval_event import ApprovalEvent
from app.models.audit_log import AuditLog
from app.models.role import Role
from app.models.user import User
from app.models.work_ai import AiProposal, WorkAiSetting, WorkAutonomyGrant
from app.models.workgraph import Task
from app.schemas.approval import ApprovalCreate, ApprovalEdit
from app.schemas.execution import ExecutionRequest
from app.services.approval.approval_service import approval_service
from app.services.execution_manager import execution_manager
from app.services.work_ai import guard, pipeline
from app.services.workgraph_service import workgraph_service

API = "/api/v1/workgraph"
_REAL_CLASSIFY = pipeline._classify  # the autouse fixture below stubs the module attribute


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture(autouse=True)
def _fast_classifier(monkeypatch):
    """The real classifier's local-LLM judge stage times out when Ollama is down (~4s/call)."""
    monkeypatch.setattr(pipeline, "_classify", lambda payload: "internal")


@pytest.fixture(autouse=True)
def _reset_ai_state(test_user):
    """Kill switch / grants persist in the shared DB; leave them clean."""
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


@pytest.fixture(scope="module")
def other():
    """A second user: returns (user_id_str, client)."""
    s = SessionLocal()
    try:
        role = s.query(Role).filter(Role.name == "user").first()
        u = User(name="Work AI Other", email=f"work-ai-other-{secrets.token_hex(5)}@example.com",
                 password_hash=hash_password(secrets.token_urlsafe(24)), role_id=role.id)
        s.add(u)
        s.commit()
        s.refresh(u)
        token, _, _ = create_access_token({"sub": str(u.id), "email": u.email, "role": "user"})
        uid = str(u.id)
    finally:
        s.close()
    c = TestClient(app)
    c.headers.update({"Authorization": f"Bearer {token}"})
    return uid, c


def _oid(u):
    return str(u.id)


def _project(db, owner, name="P"):
    return workgraph_service.create_project(db, owner, f"{name}-{secrets.token_hex(3)}")


def _propose(db, owner, project=None, title=None, **kw):
    payload = {"title": title or f"AI item {secrets.token_hex(3)}"}
    if project is not None:
        payload["project_id"] = project.id
    return pipeline.create_proposal(
        db, owner, kind=kw.pop("kind", "create_item"), payload=kw.pop("payload", payload),
        agent=kw.pop("agent", "capture"), source=kw.pop("source", "user_command"),
        confidence=kw.pop("confidence", 0.8), explanation="test", **kw,
    )


def _exec(db, owner, task_type, input_, approval_id=None, meta=None):
    return execution_manager.execute(
        db=db,
        request=ExecutionRequest(task_type=task_type, input=input_, approval_id=approval_id, metadata=meta),
        owner_id=owner,
    )


def _tasks_from(db, owner, proposal_id):
    return db.query(Task).filter(Task.owner_id == owner, Task.source_ref == proposal_id).all()


# ------------------------------------------------------------ proposal != execution

def test_proposal_creation_never_mutates_workgraph(db, test_user):
    owner = _oid(test_user)
    p = _propose(db, owner)
    assert p.status == "PENDING" and p.autonomy_level == "L1" and p.approval_id
    assert p.privacy_tier
    assert _tasks_from(db, owner, p.id) == []
    a = db.get(Approval, p.approval_id)
    assert a.status == "pending" and a.action_type == "work.create_item" and a.user_id == test_user.id


def test_approve_executes_with_full_ai_provenance_and_audit(auth_client, db, test_user):
    owner = _oid(test_user)
    proj = _project(db, owner)
    p = _propose(db, owner, proj, title="Fix OAuth redirect", agent="capture", confidence=0.72)

    r = auth_client.post(f"{API}/inbox/{p.id}/approve")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "EXECUTED" and r.json()["decided_by"] == f"user:{owner}"

    [task] = _tasks_from(db, owner, p.id)
    assert (task.created_by, task.created_by_actor) == ("ai", "agent:capture")
    assert (task.source_type, task.source_ref, task.ai_confidence) == ("ai_proposal", p.id, 0.72)
    assert task.project_id == proj.id and task.owner_id == owner

    db.expire_all()
    a = db.get(Approval, p.approval_id)
    assert a.status in ("executed", "completed")
    events = [e.event_type for e in db.query(ApprovalEvent).filter(ApprovalEvent.approval_id == a.id)]
    assert "CREATED" in events and "APPROVED" in events
    assert db.query(AuditLog).filter(
        AuditLog.user_id == test_user.id, AuditLog.action.like("execution.work.create_item:%")
    ).count() >= 1


def test_client_payload_cannot_forge_provenance_or_owner(auth_client, db, test_user):
    owner = _oid(test_user)
    p = pipeline.create_proposal(
        db, owner, kind="create_item", agent="capture", source="user_command", confidence=0.4,
        payload={"title": "forge", "created_by": "human", "created_by_actor": "user:1",
                 "owner_id": "999999", "ai_confidence": 1.0, "source_type": "manual", "source_ref": "x"},
    )
    assert "owner_id" not in p.payload and "created_by" not in p.payload
    auth_client.post(f"{API}/inbox/{p.id}/approve")
    [task] = _tasks_from(db, owner, p.id)
    assert task.owner_id == owner and task.created_by == "ai" and task.ai_confidence == 0.4
    assert task.source_type == "ai_proposal"


# ------------------------------------------------------------ approval bypass sweep

def test_no_approval_pending_approval_and_rejected_approval_all_fail(db, test_user):
    owner = _oid(test_user)
    p = _propose(db, owner)

    # 1. no approval id at all
    r = _exec(db, owner, "work.create_item", {"title": "x", "proposal_id": p.id})
    assert r.status.value == "FAILED" and r.error_type == "PermissionError"

    # 2. pending approval
    meta = {"approval_id": p.approval_id, "proposal_id": p.id}
    r = _exec(db, owner, "work.create_item", {"title": "x", "proposal_id": p.id}, p.approval_id, meta)
    assert r.status.value == "FAILED"

    # 3. rejected approval
    approval_service.reject(db, p.approval_id, test_user.id, f"ws_user_{owner}")
    r = _exec(db, owner, "work.create_item", {"title": "x", "proposal_id": p.id}, p.approval_id, meta)
    assert r.status.value == "FAILED"

    assert _tasks_from(db, owner, p.id) == []
    assert db.query(Task).filter(Task.owner_id == owner, Task.title == "x", Task.created_by == "ai").count() == 0


def test_approved_approval_without_a_real_proposal_is_refused(db, test_user):
    """A hand-made approved Approval (no ai_proposals row) still cannot mutate."""
    owner = _oid(test_user)
    ws = f"ws_user_{owner}"
    a = approval_service.create_approval(
        db, test_user.id, ws,
        ApprovalCreate(action_type="work.create_item", title="forged", payload={"title": "forged", "proposal_id": "prop_nope"}),
    )
    approval_service.approve(db, a.id, test_user.id, ws)
    r = _exec(db, owner, "work.create_item", {"title": "forged", "proposal_id": "prop_nope"}, a.id,
              {"approval_id": a.id, "proposal_id": "prop_nope"})
    assert r.status.value == "FAILED" and r.error_type == "PermissionError"
    assert db.query(Task).filter(Task.owner_id == owner, Task.title == "forged").count() == 0


def test_approval_from_another_proposal_cannot_be_reused(db, test_user):
    """
    The executor ignores the request's input and runs the *approved payload*, so
    presenting approval A with proposal B's id can only ever execute proposal A
    (as approved) -- never B, and never the attacker-supplied title.
    """
    owner = _oid(test_user)
    a, b = _propose(db, owner, title="approved-a"), _propose(db, owner, title="never-b")
    ws = f"ws_user_{owner}"
    approval_service.approve(db, a.approval_id, test_user.id, ws)
    _exec(db, owner, "work.create_item", {"title": "swap", "proposal_id": b.id}, a.approval_id,
          {"approval_id": a.approval_id, "proposal_id": b.id})
    assert _tasks_from(db, owner, b.id) == []
    assert db.query(Task).filter(Task.owner_id == owner, Task.title == "swap").count() == 0
    assert [t.title for t in _tasks_from(db, owner, a.id)] == ["approved-a"]
    db.expire_all()
    assert db.get(AiProposal, b.id).status == "PENDING"

    # ...and a direct handler-level mismatch (approval id != proposal's approval) is refused outright
    from app.execution.contracts import ExecutionContext
    from app.execution.work_handlers import CreateItemHandler
    ctx = ExecutionContext(owner_id=owner, execution_id="x", metadata={"approval_id": a.approval_id})
    with pytest.raises(PermissionError):
        CreateItemHandler().execute(db, ctx, {"title": "x", "proposal_id": b.id})


def test_classification_fails_closed_to_confidential(monkeypatch):
    from app.privacy import classifier as clf

    def boom(*a, **k):
        raise RuntimeError("classifier down")
    monkeypatch.setattr(clf.privacy_classifier, "classify", boom)
    assert _REAL_CLASSIFY({"title": "anything"}) == "confidential"


def test_replay_of_an_executed_proposal_executes_once(auth_client, db, test_user):
    owner = _oid(test_user)
    p = _propose(db, owner)
    assert auth_client.post(f"{API}/inbox/{p.id}/approve").json()["status"] == "EXECUTED"
    assert auth_client.post(f"{API}/inbox/{p.id}/approve").status_code == 400  # already EXECUTED
    # direct replay against the executor with the consumed approval
    r = _exec(db, owner, "work.create_item", {"title": "again", "proposal_id": p.id}, p.approval_id,
              {"approval_id": p.approval_id, "proposal_id": p.id})
    assert r.status.value == "FAILED"
    assert len(_tasks_from(db, owner, p.id)) == 1


# ------------------------------------------------------------ IDOR

def test_other_user_cannot_see_decide_or_target_owners_proposals(auth_client, db, test_user, other):
    other_id, other_client = other
    owner = _oid(test_user)
    mine = _propose(db, owner)

    assert other_client.get(f"{API}/inbox/{mine.id}").status_code == 404
    assert other_client.post(f"{API}/inbox/{mine.id}/approve").status_code == 404
    assert other_client.post(f"{API}/inbox/{mine.id}/reject").status_code == 404
    assert all(x["id"] != mine.id for x in other_client.get(f"{API}/inbox").json())
    assert auth_client.get(f"{API}/inbox/{mine.id}").json()["status"] == "PENDING"

    # attacker cannot even *propose* against the victim's project / items
    victim_proj = _project(db, owner)
    victim_task = workgraph_service.create_task(db, owner, "victim")
    for kind, payload in (
        ("create_item", {"title": "x", "project_id": victim_proj.id}),
        ("update_item", {"task_id": victim_task.id, "title": "pwn"}),
        ("link_items", {"task_id": victim_task.id, "other_task_id": victim_task.id}),
    ):
        with pytest.raises(ValueError):
            pipeline.create_proposal(db, other_id, kind=kind, payload=payload, agent="capture", source="user_command")
    assert db.query(AiProposal).filter(AiProposal.owner_id == other_id).count() == 0


def test_other_users_kill_switch_and_grants_are_independent(db, test_user, other):
    other_id, _ = other
    guard.set_enabled(db, other_id, False)
    try:
        assert guard.is_enabled(db, _oid(test_user)) is True
        _propose(db, _oid(test_user))  # unaffected
    finally:
        guard.set_enabled(db, other_id, True)


# ------------------------------------------------------------ payload tampering / edits

def test_reviewer_edit_only_changes_whitelisted_fields(auth_client, db, test_user):
    owner = _oid(test_user)
    proj, other_proj = _project(db, owner), _project(db, owner)
    p = _propose(db, owner, proj, title="orig")
    r = auth_client.post(f"{API}/inbox/{p.id}/approve", json={"edited_payload": {
        "title": "edited", "priority": "urgent", "project_id": other_proj.id, "proposal_id": "prop_x", "created_by": "human"}})
    assert r.status_code == 200, r.text
    [task] = _tasks_from(db, owner, p.id)
    assert (task.title, task.priority, task.project_id, task.created_by) == ("edited", "urgent", proj.id, "ai")


def test_tampered_approved_payload_is_revalidated_at_execution(db, test_user, other):
    """The generic approvals edit endpoint accepts any payload -- the handler must not trust it."""
    other_id, _ = other
    owner, ws = _oid(test_user), f"ws_user_{_oid(test_user)}"
    proj, proj2 = _project(db, owner), _project(db, owner)
    foreign = workgraph_service.create_project(db, other_id, "foreign")

    for evil in ({"project_id": foreign.id}, {"project_id": proj2.id}, {"depends_on": ["task_doesnotexist"]}):
        p = _propose(db, owner, proj, title="clean")
        approval_service.edit(db, p.approval_id, test_user.id, ws,
                              ApprovalEdit(edited_payload={"title": "evil", "proposal_id": p.id, **evil}))
        approval_service.approve(db, p.approval_id, test_user.id, ws)
        r = _exec(db, owner, "work.create_item", {"title": "evil", "proposal_id": p.id}, p.approval_id,
                  {"approval_id": p.approval_id, "proposal_id": p.id})
        assert r.status.value == "FAILED", evil
        assert _tasks_from(db, owner, p.id) == []
        assert db.query(Task).filter(Task.title == "evil").count() == 0


def test_invalid_payloads_are_rejected_before_a_proposal_exists(db, test_user):
    owner = _oid(test_user)
    for kind, payload in (
        ("create_item", {"title": ""}),
        ("create_item", {"title": "x", "priority": "apocalyptic"}),
        ("create_item", {"title": "x" * 300}),
        ("update_item", {"task_id": "task_nope", "title": "x"}),
        ("bogus_kind", {"title": "x"}),
        ("create_item", {"title": "x", "description": "y" * 30_000}),
    ):
        with pytest.raises(ValueError):
            _propose(db, owner, kind=kind, payload=payload)


# ------------------------------------------------------------ informational + update/link

def test_informational_proposal_has_no_approval_and_ack_mutates_nothing(auth_client, db, test_user):
    owner = _oid(test_user)
    before = db.query(Task).filter(Task.owner_id == owner).count()
    p = pipeline.create_proposal(db, owner, kind="duplicate_warning", agent="duplicate", source="capture",
                                 payload={"title": "dup?", "matches": ["task_a"]})
    assert p.approval_id is None and p.status == "PENDING"
    assert auth_client.post(f"{API}/inbox/{p.id}/approve").json()["status"] == "APPROVED"
    assert db.query(Task).filter(Task.owner_id == owner).count() == before


def test_update_and_link_go_through_the_same_gate(auth_client, db, test_user):
    owner = _oid(test_user)
    a, b = workgraph_service.create_task(db, owner, "a"), workgraph_service.create_task(db, owner, "b")

    up = pipeline.create_proposal(db, owner, kind="update_item", agent="focus", source="user_command",
                                  payload={"task_id": a.id, "priority": "urgent"}, confidence=0.9)
    assert workgraph_service.get_task(db, owner, a.id).priority == "medium"  # not yet
    assert auth_client.post(f"{API}/inbox/{up.id}/approve").json()["status"] == "EXECUTED"
    db.expire_all()
    ta = workgraph_service.get_task(db, owner, a.id)
    assert ta.priority == "urgent" and ta.ai_confidence == 0.9
    last = workgraph_service.list_activity(db, owner, a.id)[0]
    assert last.actor == "agent:focus" and last.payload["source_ref"] == up.id

    ln = pipeline.create_proposal(db, owner, kind="link_items", agent="risk", source="risk_scan",
                                  payload={"task_id": a.id, "other_task_id": b.id, "link_kind": "BLOCKED_BY"})
    assert workgraph_service.get_links(db, owner, a.id)["blocked_by"] == []
    assert auth_client.post(f"{API}/inbox/{ln.id}/approve").json()["status"] == "EXECUTED"
    assert workgraph_service.get_links(db, owner, a.id)["blocked_by"] == [b.id]


def test_reject_leaves_everything_untouched(auth_client, db, test_user):
    owner = _oid(test_user)
    p = _propose(db, owner)
    assert auth_client.post(f"{API}/inbox/{p.id}/reject", json={"reason": "no"}).json()["status"] == "REJECTED"
    db.expire_all()
    assert db.get(Approval, p.approval_id).status == "rejected"
    assert _tasks_from(db, owner, p.id) == []
    assert auth_client.post(f"{API}/inbox/{p.id}/approve").status_code == 400


# ------------------------------------------------------------ kill switch

def test_kill_switch_blocks_new_and_cancels_pending_but_keeps_existing_work(auth_client, db, test_user):
    owner = _oid(test_user)
    done = _propose(db, owner)
    auth_client.post(f"{API}/inbox/{done.id}/approve")
    [existing] = _tasks_from(db, owner, done.id)
    pending = _propose(db, owner)

    r = auth_client.put(f"{API}/ai/kill-switch", json={"enabled": False})
    assert r.status_code == 200 and r.json()["cancelled"] >= 1

    db.expire_all()
    assert db.get(AiProposal, pending.id).status == "CANCELLED"
    assert db.get(Approval, pending.approval_id).status == "rejected"
    assert workgraph_service.get_task(db, owner, existing.id) is not None  # untouched

    with pytest.raises(guard.KillSwitchOff):
        _propose(db, owner)
    assert auth_client.post(f"{API}/inbox/{pending.id}/approve").status_code == 400  # cancelled
    assert auth_client.get(f"{API}/ai/settings").json()["switches"]["user"] is False

    auth_client.put(f"{API}/ai/kill-switch", json={"enabled": True})
    assert _propose(db, owner).status == "PENDING"


def test_kill_switch_stops_an_already_approved_proposal_at_the_next_checkpoint(db, test_user):
    """Approved *before* the switch flipped (and not cancelled): the handler still refuses."""
    owner, ws = _oid(test_user), f"ws_user_{_oid(test_user)}"
    p = _propose(db, owner)
    approval_service.approve(db, p.approval_id, test_user.id, ws)
    db.add(WorkAiSetting(owner_id=owner, project_id="", ai_enabled=False))  # flip without cancel_pending
    db.commit()
    r = _exec(db, owner, "work.create_item", {"title": "late", "proposal_id": p.id}, p.approval_id,
              {"approval_id": p.approval_id, "proposal_id": p.id})
    assert r.status.value == "FAILED" and r.error_type == "KillSwitchOff"
    assert _tasks_from(db, owner, p.id) == []


def test_project_kill_switch_is_scoped_to_that_project(auth_client, db, test_user):
    owner = _oid(test_user)
    off, on = _project(db, owner), _project(db, owner)
    live = _propose(db, owner, on)
    doomed = _propose(db, owner, off)
    assert auth_client.put(f"{API}/ai/kill-switch", json={"enabled": False, "project_id": off.id}).status_code == 200
    db.expire_all()
    assert db.get(AiProposal, doomed.id).status == "CANCELLED"
    assert db.get(AiProposal, live.id).status == "PENDING"
    with pytest.raises(guard.KillSwitchOff):
        _propose(db, owner, off)
    assert _propose(db, owner, on).status == "PENDING"
    # foreign / unknown project ids are refused, never trusted
    assert auth_client.put(f"{API}/ai/kill-switch", json={"enabled": False, "project_id": "proj_nope"}).status_code == 400


# ------------------------------------------------------------ autonomy

def test_default_is_l1_and_l3_needs_an_explicit_per_project_kind_grant(auth_client, db, test_user):
    owner = _oid(test_user)
    a, b = _project(db, owner), _project(db, owner)
    assert _propose(db, owner, a).status == "PENDING"  # no grant -> L1 -> waits for a human

    r = auth_client.put(f"{API}/ai/autonomy", json={"project_id": a.id, "action_kind": "create_item", "level": "L3"})
    assert r.status_code == 200

    auto = _propose(db, owner, a)
    assert auto.status == "EXECUTED" and auto.autonomy_level == "L3"
    assert auto.decided_by == f"autonomy:L3:{a.id}:create_item"
    [task] = _tasks_from(db, owner, auto.id)
    assert task.created_by == "ai" and task.source_ref == auto.id
    assert "AUTO_APPROVED_L3" in [e.event_type for e in db.query(ApprovalEvent).filter(ApprovalEvent.approval_id == auto.approval_id)]

    # grant is per project and per kind: not global
    assert _propose(db, owner, b).status == "PENDING"
    other_kind = pipeline.create_proposal(db, owner, kind="update_item", agent="x", source="user_command",
                                          payload={"task_id": task.id, "priority": "low"})
    assert other_kind.status == "PENDING"


def test_grant_changes_are_audited_and_revocable(auth_client, db, test_user):
    owner = _oid(test_user)
    proj = _project(db, owner)
    put = lambda lvl: auth_client.put(f"{API}/ai/autonomy", json={"project_id": proj.id, "action_kind": "create_item", "level": lvl})
    assert put("L3").status_code == 200 and put("L2").status_code == 200 and put("L1").status_code == 200
    actions = [a.action for a in db.query(AuditLog).filter(AuditLog.user_id == test_user.id,
               AuditLog.action.like(f"work.autonomy.%:{proj.id}:%")).order_by(AuditLog.id)]
    assert actions == [f"work.autonomy.grant:{proj.id}:create_item:L1->L3",
                       f"work.autonomy.modify:{proj.id}:create_item:L3->L2",
                       f"work.autonomy.revoke:{proj.id}:create_item:L2->L1"]
    assert guard.effective_level(db, owner, proj.id, "create_item") == "L1"
    assert _propose(db, owner, proj).status == "PENDING"


def test_grants_reject_foreign_projects_bad_kinds_and_destructive_kinds(auth_client, db, test_user, other):
    other_id, _ = other
    foreign = workgraph_service.create_project(db, other_id, "theirs")
    assert auth_client.put(f"{API}/ai/autonomy", json={"project_id": foreign.id, "action_kind": "create_item", "level": "L3"}).status_code == 400
    mine = _project(db, _oid(test_user))
    assert auth_client.put(f"{API}/ai/autonomy", json={"project_id": mine.id, "action_kind": "delete_item", "level": "L3"}).status_code == 422
    for bad in ("delete_item", "bulk_delete", "send_email", "post_webhook", "remove_link", "duplicate_warning", "unknown"):
        assert guard.l3_eligible(bad) is False, bad
        with pytest.raises(ValueError):
            guard.set_grant(db, _oid(test_user), mine.id, bad, "L3")


def test_l3_is_refused_at_the_execution_layer_even_with_a_bad_grant_row(db, test_user, monkeypatch):
    owner = _oid(test_user)
    proj = _project(db, owner)
    # a bad/legacy grant slipped into the DB directly, bypassing set_grant validation
    db.add(WorkAutonomyGrant(owner_id=owner, project_id=proj.id, action_kind="create_item", level="L3"))
    db.commit()
    monkeypatch.setattr(guard, "l3_eligible", lambda kind: False)  # kind is (now) classified destructive/high-risk

    p = _propose(db, owner, proj)
    assert p.status == "PENDING"                       # not executed
    assert _tasks_from(db, owner, p.id) == []
    assert db.get(Approval, p.approval_id).status == "pending"
    with pytest.raises(guard.AutonomyViolation):       # and the layer itself refuses
        pipeline._approve_and_run(db, p, decided_by="autonomy:L3:test", auto=True)
    assert db.query(AuditLog).filter(AuditLog.user_id == test_user.id,
                                     AuditLog.action == f"work.l3.refused:{proj.id}:create_item").count() == 1


def test_l0_forbids_proposing_mutations_and_kill_switch_beats_l3(db, test_user):
    owner = _oid(test_user)
    proj = _project(db, owner)
    guard.set_grant(db, owner, proj.id, "create_item", "L0")
    with pytest.raises(guard.AutonomyViolation):
        _propose(db, owner, proj)

    guard.set_grant(db, owner, proj.id, "create_item", "L3")
    guard.set_enabled(db, owner, False, proj.id)
    with pytest.raises(guard.KillSwitchOff):
        _propose(db, owner, proj)
    assert db.query(AiProposal).filter(AiProposal.owner_id == owner, AiProposal.project_id == proj.id).count() == 0
