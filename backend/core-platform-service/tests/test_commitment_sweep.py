"""
Commitment Sweep: chains commitment.scan -> capture() -> scan_risks() into one
autonomous loop (see app/services/work_ai/orchestrator.py::commitment_sweep).

The shared dev database accumulates old meeting-derived commitments across
runs (nothing deletes the underlying Meeting/MeetingActionItem rows once
created -- see test_commitment_scan.py, which purges only Commitment rows).
commitment.scan re-discovers those every call, so assertions here are scoped
to the specific commitment each test creates rather than to the sweep's
aggregate counts, and hold regardless of that pre-existing pollution.
"""
from unittest.mock import patch

import pytest

from app.agents.inbox_agent import inbox_agent
from app.db.database import Base, SessionLocal, engine
from app.models.commitment import Commitment
from app.models.meeting import Meeting, MeetingActionItem
from app.models.work_ai import AiProposal
from app.models.workgraph import Task
from app.services.meeting_service import meeting_service
from app.services.work_ai import orchestrator, pipeline

GMAIL_PATH = "app.execution.contracts.GoogleConnectorService.unread_messages"

SAMPLE_UNREAD = [
    {"id": "sweep-msg-1", "subject": "Re: proposal", "from": "client@example.test", "snippet": "..."},
]
SAMPLE_COMMITMENTS = [
    {"id": "sweep-msg-1", "description": "Send the revised proposal to the client", "owner": "me", "due_date": "Friday"},
]


@pytest.fixture(autouse=True)
def _fast_classifier(monkeypatch):
    """The real privacy classifier's local-LLM judge stage times out when Ollama is down."""
    monkeypatch.setattr(pipeline, "_classify", lambda payload: "internal")


def _purge(db, owner_id: str) -> None:
    """
    Also clears Meeting/MeetingActionItem rows for this owner: commitment.scan
    rediscovers every meeting action item on every call (see contracts.py's
    CommitmentScanHandler), and test_commitment_scan.py's own cleanup leaves
    those rows behind permanently -- without this, an unbounded pile-up of
    unrelated stale meeting commitments can crowd this test's one commitment
    out of the sweep's capped candidate list.
    """
    db.query(AiProposal).filter(AiProposal.owner_id == owner_id).delete()
    db.query(Commitment).filter(Commitment.owner_id == owner_id).delete()
    meeting_ids = [m.id for m in db.query(Meeting.id).filter(Meeting.owner_id == owner_id).all()]
    if meeting_ids:
        db.query(MeetingActionItem).filter(MeetingActionItem.meeting_id.in_(meeting_ids)).delete(synchronize_session=False)
        db.query(Meeting).filter(Meeting.id.in_(meeting_ids)).delete(synchronize_session=False)
    db.commit()


def _scan(monkeypatch):
    monkeypatch.setattr(inbox_agent, "extract_commitments", lambda messages, **kw: SAMPLE_COMMITMENTS)
    return patch(GMAIL_PATH, return_value=SAMPLE_UNREAD)


def _my_commitment(db, owner_id: str) -> Commitment:
    """The one commitment this test's own scan produces, distinguishable from
    whatever else the shared dev database happens to hold for this owner."""
    return (
        db.query(Commitment)
        .filter(Commitment.owner_id == owner_id, Commitment.source_type == "gmail", Commitment.source_ref == "sweep-msg-1")
        .one()
    )


def _proposals_for(db, owner_id: str, commitment_id: str) -> list[AiProposal]:
    return (
        db.query(AiProposal)
        .filter(AiProposal.owner_id == owner_id, AiProposal.kind == "create_item", AiProposal.source_ref == commitment_id)
        .all()
    )


def test_sweep_drafts_a_proposal_for_a_new_commitment(test_user, monkeypatch):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        _purge(db, owner)
        tasks_before = db.query(Task).filter(Task.owner_id == owner).count()

        with _scan(monkeypatch):
            result = orchestrator.commitment_sweep(db, owner)

        assert result["proposals_created"] >= 1
        assert len(result["steps"]) == 3

        commitment = _my_commitment(db, owner)
        props = _proposals_for(db, owner, commitment.id)
        assert len(props) == 1
        assert props[0].source == "email"
        assert props[0].status == "PENDING", "sweep must never auto-execute a commitment-sourced draft"

        # never auto-executes: no task exists until a human approves
        assert db.query(Task).filter(Task.owner_id == owner).count() == tasks_before
    finally:
        _purge(db, owner)
        db.close()


def test_sweep_is_idempotent_across_reruns(test_user, monkeypatch):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        _purge(db, owner)

        with _scan(monkeypatch):
            first = orchestrator.commitment_sweep(db, owner)
            second = orchestrator.commitment_sweep(db, owner)

        assert first["proposals_created"] >= 1
        assert second["proposals_created"] == 0, "a rerun must skip, not re-propose, already-pending commitments"
        assert second["skipped_already_proposed"] == first["proposals_created"]

        commitment = _my_commitment(db, owner)
        props = _proposals_for(db, owner, commitment.id)
        assert len(props) == 1, "the commitment must still have exactly one proposal, not a second one"
    finally:
        _purge(db, owner)
        db.close()


def test_sweep_skips_a_commitment_already_linked_to_a_task(test_user, monkeypatch):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        _purge(db, owner)
        meeting = meeting_service.create_meeting(db=db, owner_id=owner, transcript_text="x")
        meeting_service.store_extraction(db, meeting, {
            "action_items": [{"description": "Already tracked manually elsewhere", "owner": "Bob", "due_date": "Monday"}],
        })
        item = meeting_service.list_action_items(db, meeting.id)[0]
        task = Task(owner_id=owner, title="Already tracked manually elsewhere")
        db.add(task)
        db.commit()
        meeting_service.link_action_item_task(db, item, task.id)

        with _scan(monkeypatch):
            orchestrator.commitment_sweep(db, owner)

        commitment = (
            db.query(Commitment)
            .filter(Commitment.owner_id == owner, Commitment.source_type == "meeting", Commitment.source_ref == item.id)
            .one()
        )
        assert commitment.linked_task_id == task.id
        props = _proposals_for(db, owner, commitment.id)
        assert not props, "a commitment already linked to a task must never get a draft proposal"
    finally:
        _purge(db, owner)
        db.close()
