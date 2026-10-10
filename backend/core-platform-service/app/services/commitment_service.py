"""
Commitment service: upsert + status computation over app/models/commitment.py.

Mirrors workgraph_service.py's shape (a thin class over direct DB queries).
Upserts are keyed on (owner_id, source_type, source_ref) -- the unique
constraint the migration adds -- so rescanning the same Gmail message or
meeting action item updates the existing row rather than creating a second
one. This module never creates a WorkGraph task; `linked_task_id` only ever
reflects a link that already exists (a meeting action item's
workgraph_task_id), matched by source_ref, never created here.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.models.commitment import Commitment
from app.models.workgraph import Task

AT_RISK_WINDOW_DAYS = 2


def _parse_iso_date(due_date: Optional[str]) -> Optional[datetime]:
    """
    Best-effort parse of a strict ISO date ("2026-09-20"). Free-text due
    dates extracted from prose ("next Friday", "EOW") are not parsed here --
    ponytail: no NL date parser dependency added for this; a due_date that
    doesn't parse this way simply can't drive at-risk status by date and
    stays governed by the linked task's own due_date/status instead.
    """
    if not due_date:
        return None
    try:
        return datetime.fromisoformat(due_date.strip()).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


class CommitmentService:

    @staticmethod
    def _compute_status(due_date: Optional[str], linked_task: Optional[Task]) -> str:
        if linked_task is not None and linked_task.status == "done":
            return "completed"

        now = datetime.now(timezone.utc)
        task_due = None
        if linked_task is not None and linked_task.due_date is not None:
            task_due = linked_task.due_date if linked_task.due_date.tzinfo else linked_task.due_date.replace(tzinfo=timezone.utc)
        own_due = _parse_iso_date(due_date)
        effective_due = task_due or own_due

        if effective_due is not None and effective_due < now + timedelta(days=AT_RISK_WINDOW_DAYS):
            return "at_risk"
        return "pending"

    @staticmethod
    def upsert_commitment(
        db: Session,
        owner_id: str,
        description: str,
        source_type: str,
        source_ref: str,
        responsible_party: Optional[str] = None,
        due_date: Optional[str] = None,
        linked_task_id: Optional[str] = None,
    ) -> tuple[Commitment, bool]:
        """Returns (row, created)."""
        linked_task = None
        if linked_task_id:
            linked_task = db.query(Task).filter(Task.id == linked_task_id, Task.owner_id == owner_id).first()
        status = CommitmentService._compute_status(due_date, linked_task)

        existing = (
            db.query(Commitment)
            .filter(
                Commitment.owner_id == owner_id,
                Commitment.source_type == source_type,
                Commitment.source_ref == source_ref,
            )
            .first()
        )
        if existing:
            existing.description = description
            existing.responsible_party = responsible_party
            existing.due_date = due_date
            existing.linked_task_id = linked_task_id
            existing.status = status
            db.commit()
            db.refresh(existing)
            return existing, False

        row = Commitment(
            owner_id=owner_id,
            description=description,
            responsible_party=responsible_party,
            due_date=due_date,
            source_type=source_type,
            source_ref=source_ref,
            status=status,
            linked_task_id=linked_task_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row, True

    @staticmethod
    def list_commitments(db: Session, owner_id: str, status: Optional[str] = None) -> list[Commitment]:
        query = db.query(Commitment).filter(Commitment.owner_id == owner_id)
        if status:
            query = query.filter(Commitment.status == status)
        return query.order_by(Commitment.created_at.desc()).all()


commitment_service = CommitmentService()
