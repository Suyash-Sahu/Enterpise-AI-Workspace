"""
Commitment Tracker: upsert idempotency + status computation.

Mirrors test_digest.py's pattern (real rows for a real test_user, purged in a
finally block) rather than mocking the DB layer under test.
"""
from datetime import datetime, timedelta, timezone

from app.db.database import Base, SessionLocal, engine
from app.models.commitment import Commitment
from app.services.commitment_service import commitment_service
from app.services.workgraph_service import workgraph_service


def _purge(db, owner_id: str, source_refs: set[str]) -> None:
    for row in db.query(Commitment).filter(Commitment.owner_id == owner_id).all():
        if row.source_ref in source_refs:
            db.delete(row)
    db.commit()


def test_upsert_is_idempotent_on_owner_source_type_source_ref(test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    ref = "msg-idempotent-1"
    try:
        _purge(db, owner, {ref})
        first, created1 = commitment_service.upsert_commitment(
            db=db, owner_id=owner, description="Send the report", source_type="gmail",
            source_ref=ref, responsible_party="Alice", due_date=None,
        )
        second, created2 = commitment_service.upsert_commitment(
            db=db, owner_id=owner, description="Send the updated report", source_type="gmail",
            source_ref=ref, responsible_party="Alice", due_date=None,
        )

        assert created1 is True
        assert created2 is False, "a rescan of the same source must update, not duplicate"
        assert first.id == second.id
        assert second.description == "Send the updated report"

        rows = [c for c in commitment_service.list_commitments(db, owner) if c.source_ref == ref]
        assert len(rows) == 1
    finally:
        _purge(db, owner, {ref})
        db.close()


def test_status_is_completed_when_linked_task_is_done(test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    ref = "mai-completed-1"
    task_title = "commitment-status-task-done"
    try:
        _purge(db, owner, {ref})
        task = workgraph_service.create_task(db=db, owner_id=owner, title=task_title)
        workgraph_service.update_task(db=db, owner_id=owner, task_id=task.id, status="done")

        row, _ = commitment_service.upsert_commitment(
            db=db, owner_id=owner, description="Ship the feature", source_type="meeting",
            source_ref=ref, linked_task_id=task.id,
        )
        assert row.status == "completed"
    finally:
        _purge(db, owner, {ref})
        db.close()


def test_status_is_at_risk_when_due_within_window_and_not_done(test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    ref = "msg-at-risk-1"
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    try:
        _purge(db, owner, {ref})
        row, _ = commitment_service.upsert_commitment(
            db=db, owner_id=owner, description="Reply with pricing", source_type="gmail",
            source_ref=ref, due_date=tomorrow,
        )
        assert row.status == "at_risk"
    finally:
        _purge(db, owner, {ref})
        db.close()


def test_status_is_pending_when_due_date_is_far_out(test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    ref = "msg-pending-1"
    far = (datetime.now(timezone.utc) + timedelta(days=30)).date().isoformat()
    try:
        _purge(db, owner, {ref})
        row, _ = commitment_service.upsert_commitment(
            db=db, owner_id=owner, description="Quarterly review prep", source_type="gmail",
            source_ref=ref, due_date=far,
        )
        assert row.status == "pending"
    finally:
        _purge(db, owner, {ref})
        db.close()
