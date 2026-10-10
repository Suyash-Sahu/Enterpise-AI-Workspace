"""
Phase 16: proactive daily digest.

Gmail and Calendar are patched at the handler's own import site (no network
in tests), but WorkGraph tasks are real rows for a real owner -- the
per-user scoping requirement is the security-relevant claim of this phase,
and mocking the thing under test would prove nothing about it.

The end-to-end test uses run_automation_task.apply() (in-process, no broker)
for the same reason test_automation_engine.py does.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.db.database import Base, SessionLocal, engine
from app.execution.contracts import DigestHandler, ExecutionContext
from app.execution.registry import task_registry
from app.models.workgraph import Task
from app.services.automation_service import (
    DIGEST_AUTOMATION_NAME,
    DIGEST_CAPABILITY,
    automation_service,
)
from app.services.workgraph_service import workgraph_service
from app.workers.tasks import run_automation_task

API = "/api/v1/automations"

GMAIL_PATH = "app.execution.contracts.GoogleConnectorService.unread_messages"
CALENDAR_PATH = "app.execution.contracts.CalendarService.list_events"

SAMPLE_UNREAD = [
    {"subject": "Invoice overdue", "from": "billing@example.test", "snippet": "Payment due"},
    {"subject": "Standup notes", "from": "team@example.test", "snippet": "Yesterday we"},
]


def _event(summary: str, start_hour: int, end_hour: int) -> dict:
    day = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    return {
        "summary": summary,
        "start": {"dateTime": day.replace(hour=start_hour).isoformat()},
        "end": {"dateTime": day.replace(hour=end_hour).isoformat()},
    }


def _context(owner_id: str) -> ExecutionContext:
    return ExecutionContext(owner_id=owner_id, execution_id="exec_digest_test")


def _purge_tasks(db, owner_id: str, titles: set[str]) -> None:
    for task in db.query(Task).filter(Task.owner_id == owner_id).all():
        if task.title in titles:
            db.delete(task)
    db.commit()


# --- Handler composition ----------------------------------------------------


def test_digest_composes_all_three_sections(test_user):
    with patch(GMAIL_PATH, return_value=SAMPLE_UNREAD), \
         patch(CALENDAR_PATH, return_value=[_event("Standup", 9, 10)]):
        out = DigestHandler().execute(SessionLocal(), _context(str(test_user.id)), {})

    result = out["result"]
    assert result["unread_email"]["available"] is True
    assert result["unread_email"]["count"] == 2
    assert result["today_events"]["available"] is True
    assert result["today_events"]["count"] == 1
    assert result["overdue_tasks"]["available"] is True
    assert "Unread email: 2" in result["summary"]


def test_digest_detects_overlapping_calendar_events(test_user):
    overlapping = [_event("Standup", 9, 11), _event("Design review", 10, 12)]
    with patch(GMAIL_PATH, return_value=[]), patch(CALENDAR_PATH, return_value=overlapping):
        out = DigestHandler().execute(SessionLocal(), _context(str(test_user.id)), {})

    conflicts = out["result"]["today_events"]["conflicts"]
    assert len(conflicts) == 1
    assert {conflicts[0]["event_a"], conflicts[0]["event_b"]} == {"Standup", "Design review"}
    assert "conflict:" in out["result"]["summary"]


def test_digest_does_not_report_back_to_back_events_as_conflicting(test_user):
    back_to_back = [_event("Standup", 9, 10), _event("Design review", 10, 11)]
    with patch(GMAIL_PATH, return_value=[]), patch(CALENDAR_PATH, return_value=back_to_back):
        out = DigestHandler().execute(SessionLocal(), _context(str(test_user.id)), {})

    assert out["result"]["today_events"]["conflicts"] == []


def test_digest_reports_an_unavailable_connector_instead_of_reporting_zero(test_user):
    """
    The honesty property: a disconnected Gmail account must not render as
    "Unread email: 0", which is a wrong answer presented as a real one.
    """
    with patch(GMAIL_PATH, side_effect=RuntimeError("google token expired")), \
         patch(CALENDAR_PATH, return_value=[]):
        out = DigestHandler().execute(SessionLocal(), _context(str(test_user.id)), {})

    email_section = out["result"]["unread_email"]
    assert email_section["available"] is False
    assert "google token expired" in email_section["reason"]
    assert "count" not in email_section
    assert "Unread email: unavailable" in out["result"]["summary"]
    # One failed section must not take the others down with it.
    assert out["result"]["today_events"]["available"] is True


def test_digest_rejects_an_owner_id_that_is_not_a_real_account():
    try:
        DigestHandler().execute(SessionLocal(), _context("not-a-user-id"), {})
    except ValueError as exc:
        assert "not a users.id" in str(exc)
    else:
        raise AssertionError("expected a ValueError for a non-account owner_id")


# --- Per-user scoping (the security requirement) ----------------------------


def test_digest_overdue_tasks_are_scoped_to_the_requesting_owner_only(test_user):
    """
    PHASE_16.md Security Considerations: "Confirm no cross-user data leak in
    the aggregation step." Two owners each get a real overdue task; the
    digest for one must contain only that one's task.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    mine, theirs = "digest-mine-overdue", "digest-theirs-overdue"
    other_owner = "999999"
    past = datetime.now(timezone.utc) - timedelta(days=2)
    try:
        _purge_tasks(db, str(test_user.id), {mine})
        _purge_tasks(db, other_owner, {theirs})
        workgraph_service.create_task(db=db, owner_id=str(test_user.id), title=mine, due_date=past)
        workgraph_service.create_task(db=db, owner_id=other_owner, title=theirs, due_date=past)

        with patch(GMAIL_PATH, return_value=[]), patch(CALENDAR_PATH, return_value=[]):
            out = DigestHandler().execute(db, _context(str(test_user.id)), {})

        titles = [t["title"] for t in out["result"]["overdue_tasks"]["items"]]
        assert mine in titles
        assert theirs not in titles
    finally:
        _purge_tasks(db, str(test_user.id), {mine})
        _purge_tasks(db, other_owner, {theirs})
        db.close()


def test_digest_excludes_done_and_not_yet_due_tasks(test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    overdue, done, future = "digest-overdue", "digest-done", "digest-future"
    titles = {overdue, done, future}
    owner = str(test_user.id)
    try:
        _purge_tasks(db, owner, titles)
        past = datetime.now(timezone.utc) - timedelta(days=1)
        soon = datetime.now(timezone.utc) + timedelta(days=1)
        workgraph_service.create_task(db=db, owner_id=owner, title=overdue, due_date=past)
        done_task = workgraph_service.create_task(db=db, owner_id=owner, title=done, due_date=past)
        workgraph_service.update_task(db=db, owner_id=owner, task_id=done_task.id, status="done")
        workgraph_service.create_task(db=db, owner_id=owner, title=future, due_date=soon)

        with patch(GMAIL_PATH, return_value=[]), patch(CALENDAR_PATH, return_value=[]):
            out = DigestHandler().execute(db, _context(owner), {})

        reported = [t["title"] for t in out["result"]["overdue_tasks"]["items"]]
        assert overdue in reported
        assert done not in reported
        assert future not in reported
    finally:
        _purge_tasks(db, owner, titles)
        db.close()


# --- Registration & opt-in --------------------------------------------------


# --- Morning Brief enrichment (upcoming deadlines / at-risk commitments) ----


def test_digest_includes_upcoming_deadlines_and_suggested_actions(test_user):
    from app.services.commitment_service import commitment_service
    from app.models.commitment import Commitment

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    soon_title = "digest-upcoming-deadline"
    ref = "commit-digest-at-risk"
    try:
        _purge_tasks(db, owner, {soon_title})
        for row in db.query(Commitment).filter(Commitment.owner_id == owner, Commitment.source_ref == ref).all():
            db.delete(row)
        db.commit()

        workgraph_service.create_task(
            db=db, owner_id=owner, title=soon_title,
            due_date=datetime.now(timezone.utc) + timedelta(days=1),
        )
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        commitment_service.upsert_commitment(
            db=db, owner_id=owner, description="Reply with pricing", source_type="gmail",
            source_ref=ref, due_date=tomorrow,
        )

        with patch(GMAIL_PATH, return_value=SAMPLE_UNREAD), patch(CALENDAR_PATH, return_value=[]):
            out = DigestHandler().execute(db, _context(owner), {})

        result = out["result"]
        assert result["upcoming_deadlines"]["available"] is True
        assert soon_title in [t["title"] for t in result["upcoming_deadlines"]["items"]]

        assert result["at_risk_commitments"]["available"] is True
        assert ref in [c["id"] for c in result["at_risk_commitments"]["items"]] or result["at_risk_commitments"]["count"] >= 1

        assert isinstance(result["suggested_actions"], list)
        assert any("at-risk commitment" in a for a in result["suggested_actions"])
    finally:
        _purge_tasks(db, owner, {soon_title})
        for row in db.query(Commitment).filter(Commitment.owner_id == owner, Commitment.source_ref == ref).all():
            db.delete(row)
        db.commit()
        db.close()


def test_digest_capability_is_registered_read_only_and_needs_no_approval():
    handler = task_registry.get_handler(DIGEST_CAPABILITY)
    assert handler.metadata.side_effect == "read_only"
    assert handler.metadata.requires_human_approval is False


def test_enable_daily_digest_is_idempotent(test_user):
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        first = automation_service.enable_daily_digest(db=db, owner_id=owner)
        second = automation_service.enable_daily_digest(db=db, owner_id=owner, schedule="30 7 * * *")

        assert second.id == first.id, "opting in twice must not create a second digest"
        assert second.schedule == "30 7 * * *"
        assert second.enabled is True

        matching = [
            a for a in automation_service.list_automations(db=db, owner_id=owner)
            if a.name == DIGEST_AUTOMATION_NAME
        ]
        assert len(matching) == 1

        disabled = automation_service.disable_daily_digest(db=db, owner_id=owner)
        assert disabled.enabled is False
        assert disabled.id == first.id  # disabled, not deleted
    finally:
        db.close()


def test_digest_opt_in_toggle_via_api(auth_client):
    enabled = auth_client.post(f"{API}/digest/enable")
    assert enabled.status_code == 200, enabled.text
    body = enabled.json()
    assert body["enabled"] is True
    assert body["trigger_type"] == "schedule"
    assert body["steps"][0]["capability"] == DIGEST_CAPABILITY

    disabled = auth_client.post(f"{API}/digest/disable")
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False


# --- End-to-end scheduled run (Definition of Done) --------------------------


def test_scheduled_digest_automation_runs_end_to_end_and_is_owner_scoped(test_user):
    """
    PHASE_16.md Definition of Done: "A real scheduled Automation run
    produces a correct, per-user-scoped digest."
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    mine = "digest-e2e-overdue"
    try:
        _purge_tasks(db, owner, {mine})
        workgraph_service.create_task(
            db=db, owner_id=owner, title=mine,
            due_date=datetime.now(timezone.utc) - timedelta(days=3),
        )
        automation = automation_service.enable_daily_digest(db=db, owner_id=owner)
        automation_id = automation.id
        assert automation.trigger_type == "schedule"
    finally:
        db.close()

    with patch(GMAIL_PATH, return_value=SAMPLE_UNREAD), \
         patch(CALENDAR_PATH, return_value=[_event("Standup", 9, 10)]):
        result = run_automation_task.apply(args=[automation_id]).get()

    # Read-only capability: completes outright, never parks on an approval.
    assert result["status"] == "COMPLETED", result
    assert result.get("approval_id") is None

    db2 = SessionLocal()
    try:
        refreshed = automation_service.get_automation(db=db2, owner_id=owner, automation_id=automation_id)
        history = automation_service.to_response_dto(refreshed).execution_history
        assert history[-1]["status"] == "COMPLETED"
        assert refreshed.owner_id == owner

        # Delivery: the run's digest is readable back for this owner, and
        # carries the real per-user content the run produced.
        delivered = automation_service.latest_digest(db=db2, owner_id=owner)
        assert delivered is not None
        digest = delivered["digest"]
        assert digest["owner_id"] == owner
        assert digest["unread_email"]["count"] == 2
        assert mine in [t["title"] for t in digest["overdue_tasks"]["items"]]

        # ...and is not readable by anyone else.
        assert automation_service.latest_digest(db=db2, owner_id="999999") is None
    finally:
        _purge_tasks(db2, owner, {mine})
        db2.close()
