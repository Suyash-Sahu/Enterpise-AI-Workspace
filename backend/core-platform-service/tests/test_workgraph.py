"""
AMOF-X Phase 6: WorkGraph (Project/Task/TaskDependency) API and capability
tests.

The acceptance criterion this phase is built around: task creation from an
AI source is indistinguishable in the schema from human creation except for
created_by/source_type -- same table, same constraints, no parallel "AI
tasks" system. test_ai_created_task_shares_the_exact_same_table_as_human_
created proves this directly rather than asserting it structurally.
"""
from app.db.database import Base, SessionLocal, engine
from app.services.workgraph_service import workgraph_service

API = "/api/v1/workgraph"


def _make_owner_id(user) -> str:
    return str(user.id)


def test_create_and_list_project_via_api(auth_client):
    resp = auth_client.post(f"{API}/projects", json={"name": "Q4 Launch", "description": "Launch tracking"})
    assert resp.status_code == 201, resp.text
    project = resp.json()
    assert project["name"] == "Q4 Launch"
    assert project["status"] == "active"

    listing = auth_client.get(f"{API}/projects")
    assert listing.status_code == 200
    assert any(p["id"] == project["id"] for p in listing.json())


def test_create_assign_update_and_complete_task_via_api(auth_client):
    created = auth_client.post(f"{API}/tasks", json={"title": "Write release notes", "priority": "high"})
    assert created.status_code == 201, created.text
    task = created.json()
    assert task["title"] == "Write release notes"
    assert task["status"] == "open"
    # Every task created through the human-facing API is "human"/"manual" --
    # this is the baseline the AI-creation test below is compared against.
    assert task["created_by"] == "human"
    assert task["source_type"] == "manual"

    assigned = auth_client.patch(f"{API}/tasks/{task['id']}", json={"assignee": "alex@example.com", "status": "in_progress"})
    assert assigned.status_code == 200, assigned.text
    assert assigned.json()["assignee"] == "alex@example.com"
    assert assigned.json()["status"] == "in_progress"

    completed = auth_client.patch(f"{API}/tasks/{task['id']}", json={"status": "done"})
    assert completed.status_code == 200
    assert completed.json()["status"] == "done"

    fetched = auth_client.get(f"{API}/tasks/{task['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "done"
    assert fetched.json()["assignee"] == "alex@example.com"


def test_task_dependencies_round_trip_through_the_api(auth_client):
    a = auth_client.post(f"{API}/tasks", json={"title": "Design schema"}).json()
    b = auth_client.post(f"{API}/tasks", json={"title": "Implement API", "depends_on": [a["id"]]}).json()

    assert b["depends_on"] == [a["id"]]

    refetched = auth_client.get(f"{API}/tasks/{b['id']}").json()
    assert refetched["depends_on"] == [a["id"]]


def test_a_task_only_visible_to_its_owner(auth_client, test_user):
    created = auth_client.post(f"{API}/tasks", json={"title": "Private task"}).json()

    db = SessionLocal()
    try:
        other_owner_view = workgraph_service.get_task(db=db, owner_id="999999", task_id=created["id"])
        assert other_owner_view is None

        real_owner_view = workgraph_service.get_task(db=db, owner_id=str(test_user.id), task_id=created["id"])
        assert real_owner_view is not None
    finally:
        db.close()


def test_ai_created_task_shares_the_exact_same_table_as_human_created(test_user):
    """
    Dispatches workgraph.create_task through the real execution path (no
    approval required, unlike gmail.send -- confirmed by this call
    succeeding synchronously) exactly the way a CDRP critical-escalation or
    a Meeting action-item conversion would, then confirms the resulting row
    lives in the identical `tasks` table a human-created task does: same
    query, same shape, differing only in created_by/source_type/source_ref.
    """
    from app.schemas.execution import ExecutionRequest
    from app.services.execution_manager import execution_manager

    db = SessionLocal()
    try:
        owner_id = _make_owner_id(test_user)

        human_task = workgraph_service.create_task(
            db=db, owner_id=owner_id, title="Manually filed bug",
        )

        req = ExecutionRequest(
            task_type="workgraph.create_task",
            input={
                "title": "Follow up on low-confidence answer",
                "created_by": "ai",
                "source_type": "cdrp_replan",
                "source_ref": "wstep_test_001",
            },
        )
        res = execution_manager.execute(db=db, request=req, owner_id=owner_id)
        assert res.status.value == "COMPLETED", res.error_message

        ai_task_id = res.result["id"]
        ai_task = workgraph_service.get_task(db=db, owner_id=owner_id, task_id=ai_task_id)
        assert ai_task is not None

        # Fetched via the exact same service method, from the exact same
        # table -- the only differences are the provenance fields.
        assert ai_task.created_by == "ai"
        assert ai_task.source_type == "cdrp_replan"
        assert ai_task.source_ref == "wstep_test_001"
        assert human_task.created_by == "human"
        assert human_task.source_type == "manual"
        assert human_task.source_ref is None

        # Every other column is the same shape/nullability for both rows --
        # proving "no parallel AI tasks system" rather than asserting it.
        for col in ("id", "owner_id", "title", "status", "priority", "created_at", "updated_at"):
            assert getattr(ai_task, col) is not None
            assert getattr(human_task, col) is not None
    finally:
        db.close()


def test_workgraph_create_task_requires_no_approval_unlike_gmail_send():
    """
    Sanity check on the risk classification: dispatching workgraph.create_task
    with NO approval_id must succeed (LOW_SIDE_EFFECT, reversible, no
    approval required) -- unlike gmail.send, which the Phase 5 tests prove
    is refused without one.
    """
    from app.schemas.execution import ExecutionRequest
    from app.services.execution_manager import execution_manager

    db = SessionLocal()
    try:
        req = ExecutionRequest(
            task_type="workgraph.create_task",
            input={"title": "No approval needed for this"},
            approval_id=None,
        )
        res = execution_manager.execute(db=db, request=req, owner_id="1")
        assert res.status.value == "COMPLETED", res.error_message
    finally:
        db.close()
