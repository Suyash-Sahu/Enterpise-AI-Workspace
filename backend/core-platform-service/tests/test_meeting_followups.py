"""
Meeting -> Task -> Follow-up: GET /meetings/follow-ups.
"""
from datetime import datetime, timedelta, timezone

from app.db.database import Base, SessionLocal, engine
from app.models.workgraph import Task
from app.services.workgraph_service import workgraph_service

API = "/api/v1/meetings"


def _purge(db, owner_id: str, titles: set[str]) -> None:
    for task in db.query(Task).filter(Task.owner_id == owner_id).all():
        if task.title in titles:
            db.delete(task)
    db.commit()


def test_follow_ups_include_overdue_and_due_soon_meeting_tasks_only(auth_client, test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    overdue, due_soon, far_out, done, non_meeting = (
        "follow-up-overdue", "follow-up-due-soon", "follow-up-far-out",
        "follow-up-done", "follow-up-non-meeting",
    )
    titles = {overdue, due_soon, far_out, done, non_meeting}
    now = datetime.now(timezone.utc)
    try:
        _purge(db, owner, titles)
        workgraph_service.create_task(
            db=db, owner_id=owner, title=overdue, due_date=now - timedelta(days=1),
            source_type="meeting_action_item",
        )
        workgraph_service.create_task(
            db=db, owner_id=owner, title=due_soon, due_date=now + timedelta(days=1),
            source_type="meeting_action_item",
        )
        workgraph_service.create_task(
            db=db, owner_id=owner, title=far_out, due_date=now + timedelta(days=30),
            source_type="meeting_action_item",
        )
        done_task = workgraph_service.create_task(
            db=db, owner_id=owner, title=done, due_date=now - timedelta(days=1),
            source_type="meeting_action_item",
        )
        workgraph_service.update_task(db=db, owner_id=owner, task_id=done_task.id, status="done")
        workgraph_service.create_task(
            db=db, owner_id=owner, title=non_meeting, due_date=now - timedelta(days=1),
            source_type="manual",
        )

        resp = auth_client.get(f"{API}/follow-ups")
        assert resp.status_code == 200, resp.text
        reported = {t["title"] for t in resp.json()}

        assert overdue in reported
        assert due_soon in reported
        assert far_out not in reported
        assert done not in reported
        assert non_meeting not in reported
    finally:
        _purge(db, owner, titles)
        db.close()
