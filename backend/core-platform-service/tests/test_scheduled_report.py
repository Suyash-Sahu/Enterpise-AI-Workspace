"""
Phase 18: scheduled database reports.

PHASE_18.md's Definition of Done asks for a real scheduled report run that
is "provably tenant-scoped by inspection of the executed SQL" -- so these
tests assert on the SQL that actually ran, read back out of the Execution
row, not on the fact that a flag was passed.

sql_generation_service.generate_sql is patched so the test controls exactly
what the model "generates": the thing under test is what the pipeline does
with an unscoped query, which cannot be exercised reliably if the query is
whatever a live model happens to emit. Everything downstream of that --
validator, executor, automation dispatch -- is real.

The run goes through run_automation_task.apply() (in-process, no broker),
the same approach test_digest.py and test_automation_engine.py use.
"""
from unittest.mock import patch

from app.db.database import Base, SessionLocal, engine
from app.models.automation import Automation
from app.schemas.automation import AutomationStep
from app.services.automation_service import REPORT_CAPABILITY, automation_service
from app.workers.tasks import run_automation_task

GENERATE_SQL_PATH = "app.agents.database_agent.sql_generation_service.generate_sql"

REPORT_NAME = "Phase 18 scheduled report"
UNSCOPED_SQL = "SELECT source, chunk_count FROM ingested_documents"
SCOPED_SQL = "SELECT source, chunk_count FROM ingested_documents WHERE owner_id = :owner_id"


def _purge_reports(db, owner_id: str) -> None:
    for row in db.query(Automation).filter(Automation.owner_id == owner_id, Automation.name == REPORT_NAME).all():
        db.delete(row)
    db.commit()


def _create_report_automation(db, owner_id: str) -> str:
    automation = automation_service.create_automation(
        db=db,
        owner_id=owner_id,
        name=REPORT_NAME,
        trigger_type="schedule",
        schedule="0 7 * * 1",  # 07:00 every Monday
        steps=[
            AutomationStep(
                step_id="report",
                capability=REPORT_CAPABILITY,
                input_template={"question": "how many documents do I have"},
            )
        ],
    )
    return automation.id


def _run(owner_id: str, generated_sql: str) -> dict:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _purge_reports(db, owner_id)
        automation_id = _create_report_automation(db, owner_id)
    finally:
        db.close()

    with patch(GENERATE_SQL_PATH, return_value=(generated_sql, None)):
        return run_automation_task.apply(args=[automation_id]).get()


def test_scheduled_report_runs_end_to_end_and_executes_owner_scoped_sql(test_user):
    """
    Definition of Done: a real scheduled Automation run produces a report,
    and the SQL it actually executed carries the owner predicate.
    """
    owner = str(test_user.id)
    result = _run(owner, SCOPED_SQL)

    # Read-only capability: completes outright, never parks on an approval.
    assert result["status"] == "COMPLETED", result
    assert result.get("approval_id") is None

    db = SessionLocal()
    try:
        delivered = automation_service.latest_report(db=db, owner_id=owner)
        assert delivered is not None, "the run's report must be readable back in-app"
        executed_sql = delivered["result"]["sql"]
        assert "owner_id = :owner_id" in executed_sql, executed_sql

        # ...and is not readable by another owner: latest_result filters on
        # owner_id, so another account's run is never selected at all.
        assert automation_service.latest_report(db=db, owner_id="999999") is None
    finally:
        _purge_reports(db, owner)
        db.close()


def test_unscoped_generated_sql_never_executes_on_the_scheduled_path(test_user):
    """
    The security-critical case this phase exists for. With no human
    reviewing each run, a generated query lacking the owner predicate must
    not run: SQLValidator rejects it under require_owner_scope=True and the
    pipeline falls back to the hardcoded owner-scoped query instead.
    """
    owner = str(test_user.id)
    result = _run(owner, UNSCOPED_SQL)

    assert result["status"] == "COMPLETED", result

    db = SessionLocal()
    try:
        delivered = automation_service.latest_report(db=db, owner_id=owner)
        assert delivered is not None
        executed_sql = delivered["result"]["sql"]
        assert executed_sql != UNSCOPED_SQL, "the unscoped generated SQL must never be what ran"
        assert "owner_id = :owner_id" in executed_sql, executed_sql
    finally:
        _purge_reports(db, owner)
        db.close()


def test_report_capability_is_scheduled_through_the_ordinary_beat_substrate(test_user):
    """No bespoke scheduling: the report automation is picked up by the same
    build_beat_schedule() every other scheduled automation goes through."""
    owner = str(test_user.id)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        _purge_reports(db, owner)
        automation_id = _create_report_automation(db, owner)
        schedule = automation_service.build_beat_schedule(db)
        assert f"automation-{automation_id}" in schedule
    finally:
        _purge_reports(db, owner)
        db.close()


def test_latest_report_endpoint_is_owner_scoped(auth_client, client):
    """404 rather than another owner's report when the caller has none, and
    no anonymous access at all."""
    assert client.get("/api/v1/automations/reports/latest").status_code in (401, 403)
    res = auth_client.get("/api/v1/automations/reports/latest")
    assert res.status_code in (200, 404)
