"""
AMOF-X Phase 8: Automation CRUD + run-path tests.

`run_automation_task.apply()` (not `.delay()`/`.apply_async()`) runs the
task function directly, in-process, with no broker/worker required --
exactly PHASE_08.md's own guidance for testing without waiting on real
Beat timing. The security-critical proof here is that a template resolving
to a side-effecting capability creates a pending Approval and returns
WAITING_FOR_APPROVAL rather than executing -- run_automation() has no code
path that skips it (see automation_service.py / supervisor.py's
run(preset_plan=...) docstring).
"""
from unittest.mock import patch

from app.db.database import Base, SessionLocal, engine
from app.models.approval import Approval
from app.models.workflow import WorkflowPlan, WorkflowStep
from app.schemas.automation import AutomationStep
from app.schemas.runtime import RuntimeGenerateResponse
from app.services.automation_service import automation_service
from app.workers.tasks import run_automation_task

API = "/api/v1/automations"

MOCK_RESP = RuntimeGenerateResponse(
    completion="Weekly report: all systems nominal, three tasks closed this week.",
    provider="mock_provider",
    model="mock_model",
    runtime="local",
)


def _text_gen_steps():
    return [{"step_id": "step_1", "capability": "text_generation", "depends_on": [], "input_template": {"prompt": "Summarize the week."}}]


def _gmail_send_steps():
    return [{
        "step_id": "step_1",
        "capability": "gmail.send",
        "depends_on": [],
        "input_template": {"to": "team@example.com", "subject": "Weekly report", "body": "See attached."},
    }]


def test_create_list_get_update_automation_via_api(auth_client):
    created = auth_client.post(API, json={
        "name": "Weekly summary",
        "trigger_type": "schedule",
        "schedule": "0 9 * * 1",
        "steps": _text_gen_steps(),
    })
    assert created.status_code == 201, created.text
    automation = created.json()
    assert automation["trigger_type"] == "schedule"
    assert automation["enabled"] is True
    assert automation["steps"][0]["capability"] == "text_generation"

    listing = auth_client.get(API)
    assert listing.status_code == 200
    assert any(a["id"] == automation["id"] for a in listing.json())

    fetched = auth_client.get(f"{API}/{automation['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == automation["id"]

    updated = auth_client.patch(f"{API}/{automation['id']}", json={"enabled": False})
    assert updated.status_code == 200
    assert updated.json()["enabled"] is False


def test_schedule_automation_requires_a_cron_string(auth_client):
    resp = auth_client.post(API, json={
        "name": "Broken schedule",
        "trigger_type": "schedule",
        "steps": _text_gen_steps(),
    })
    assert resp.status_code == 422


def test_automation_only_visible_to_its_owner(auth_client, test_user):
    created = auth_client.post(API, json={
        "name": "Private automation",
        "trigger_type": "schedule",
        "schedule": "0 9 * * 1",
        "steps": _text_gen_steps(),
    }).json()

    db = SessionLocal()
    try:
        other_owner_view = automation_service.get_automation(db=db, owner_id="999999", automation_id=created["id"])
        assert other_owner_view is None

        real_owner_view = automation_service.get_automation(db=db, owner_id=str(test_user.id), automation_id=created["id"])
        assert real_owner_view is not None
    finally:
        db.close()


def test_run_automation_task_produces_a_real_checkpointed_workflow(test_user):
    """A scheduled automation fires and produces a real WorkflowPlan/
    WorkflowStep (Phase 3's persistence) -- not a simulated run."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        automation = automation_service.create_automation(
            db=db, owner_id=str(test_user.id), name="Run-now summary",
            trigger_type="schedule", schedule="0 9 * * 1",
            steps=[AutomationStep(**s) for s in _text_gen_steps()],
        )
        automation_id = automation.id
    finally:
        db.close()

    with patch("app.execution.contracts.runtime_service.generate", return_value=MOCK_RESP):
        result = run_automation_task.apply(args=[automation_id]).get()

    assert result["status"] == "COMPLETED", result

    db2 = SessionLocal()
    try:
        wf_plan = db2.query(WorkflowPlan).filter(WorkflowPlan.request_id == result["request_id"]).first()
        assert wf_plan is not None
        assert wf_plan.owner_id == str(test_user.id)
        wf_steps = db2.query(WorkflowStep).filter(WorkflowStep.plan_id == wf_plan.id).all()
        assert any(s.capability == "text_generation" for s in wf_steps)

        automation = automation_service.get_automation(db=db2, owner_id=str(test_user.id), automation_id=automation_id)
        history = automation_service.to_response_dto(automation).execution_history
        assert len(history) == 1
        assert history[0]["status"] == "COMPLETED"
    finally:
        db2.close()


def test_automation_resolving_to_a_side_effecting_capability_does_not_auto_execute(test_user):
    """
    The explicit security regression PHASE_08.md names: an automation whose
    template resolves to gmail.send (requires_human_approval=True) must
    create a pending Approval and return WAITING_FOR_APPROVAL -- never send.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        automation = automation_service.create_automation(
            db=db, owner_id=str(test_user.id), name="Auto-send (should be gated)",
            trigger_type="schedule", schedule="0 9 * * 1",
            steps=[AutomationStep(**s) for s in _gmail_send_steps()],
        )
        automation_id = automation.id
    finally:
        db.close()

    with patch("app.execution.contracts.GoogleConnectorService.send_email") as mock_send:
        result = run_automation_task.apply(args=[automation_id]).get()
        mock_send.assert_not_called()

    assert result["status"] == "WAITING_FOR_APPROVAL", result
    assert result["approval_id"] is not None

    db2 = SessionLocal()
    try:
        approval = db2.query(Approval).filter(Approval.id == result["approval_id"]).first()
        assert approval is not None
        assert approval.status == "pending"
        assert approval.action_type == "gmail.send"
    finally:
        db2.close()


def test_run_automation_now_endpoint_goes_through_the_same_gate(auth_client, test_user):
    created = auth_client.post(API, json={
        "name": "Manual-run send (should be gated)",
        "trigger_type": "schedule",
        "schedule": "0 9 * * 1",
        "steps": _gmail_send_steps(),
    }).json()

    with patch("app.execution.contracts.GoogleConnectorService.send_email") as mock_send:
        resp = auth_client.post(f"{API}/{created['id']}/run")
        mock_send.assert_not_called()

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "WAITING_FOR_APPROVAL"
    assert resp.json()["approval_id"] is not None


def test_build_beat_schedule_reads_only_enabled_schedule_automations(test_user):
    db = SessionLocal()
    try:
        enabled = automation_service.create_automation(
            db=db, owner_id=str(test_user.id), name="Enabled weekly",
            trigger_type="schedule", schedule="0 9 * * 1",
            steps=[AutomationStep(**s) for s in _text_gen_steps()],
            enabled=True,
        )
        automation_service.create_automation(
            db=db, owner_id=str(test_user.id), name="Disabled weekly",
            trigger_type="schedule", schedule="0 9 * * 1",
            steps=[AutomationStep(**s) for s in _text_gen_steps()],
            enabled=False,
        )

        schedule = automation_service.build_beat_schedule(db)
        assert f"automation-{enabled.id}" in schedule
        assert schedule[f"automation-{enabled.id}"]["task"] == "app.workers.tasks.run_automation_task"
    finally:
        db.close()
