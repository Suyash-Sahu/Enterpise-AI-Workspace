"""
Commitment Tracker scan: "commitment.scan" capability.

GMAIL_PATH mirrors test_digest.py's patch site exactly (same reasoning: a
staticmethod patched on the class object affects every caller including
InboxAgent). extract_commitments is stubbed directly on the inbox_agent
singleton -- no LLM call needed to test the scan/persist wiring.
"""
from app.agents.inbox_agent import inbox_agent
from app.db.database import Base, SessionLocal, engine
from app.execution.contracts import CommitmentScanHandler, ExecutionContext
from app.models.commitment import Commitment
from app.models.workgraph import Task
from app.services.meeting_service import meeting_service

GMAIL_PATH = "app.execution.contracts.GoogleConnectorService.unread_messages"

SAMPLE_UNREAD = [
    {"id": "msg-1", "subject": "Re: proposal", "from": "client@example.test", "snippet": "..."},
]
SAMPLE_COMMITMENTS = [
    {"id": "msg-1", "description": "Send the revised proposal", "owner": "me", "due_date": "Friday"},
]


def _context(owner_id: str) -> ExecutionContext:
    return ExecutionContext(owner_id=owner_id, execution_id="exec_commitment_scan_test")


def _purge(db, owner_id: str) -> None:
    for row in db.query(Commitment).filter(Commitment.owner_id == owner_id).all():
        db.delete(row)
    db.commit()


def test_scan_never_creates_a_workgraph_task(test_user, monkeypatch):
    from unittest.mock import patch

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        _purge(db, owner)
        tasks_before = db.query(Task).filter(Task.owner_id == owner).count()

        monkeypatch.setattr(inbox_agent, "extract_commitments", lambda messages, **kw: SAMPLE_COMMITMENTS)
        with patch(GMAIL_PATH, return_value=SAMPLE_UNREAD):
            out = CommitmentScanHandler().execute(db, _context(owner), {})

        tasks_after = db.query(Task).filter(Task.owner_id == owner).count()
        assert tasks_after == tasks_before, "commitment scan must never create a WorkGraph task"
        assert out["result"]["created"] >= 1
    finally:
        _purge(db, owner)
        db.close()


def test_scan_is_idempotent_across_gmail_and_meeting_sources(test_user, monkeypatch):
    from unittest.mock import patch

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        _purge(db, owner)
        meeting = meeting_service.create_meeting(db=db, owner_id=owner, transcript_text="x")
        meeting_service.store_extraction(db, meeting, {
            "action_items": [{"description": "Draft the follow-up email", "owner": "Bob", "due_date": "Monday"}],
        })

        monkeypatch.setattr(inbox_agent, "extract_commitments", lambda messages, **kw: SAMPLE_COMMITMENTS)
        with patch(GMAIL_PATH, return_value=SAMPLE_UNREAD):
            first = CommitmentScanHandler().execute(db, _context(owner), {})
            second = CommitmentScanHandler().execute(db, _context(owner), {})

        assert first["result"]["created"] >= 2  # 1 gmail + 1 meeting item
        assert second["result"]["created"] == 0, "a rescan must update, not duplicate"

        rows = db.query(Commitment).filter(Commitment.owner_id == owner).all()
        by_source = {(r.source_type, r.source_ref) for r in rows}
        assert ("gmail", "msg-1") in by_source
        assert any(st == "meeting" for st, _ in by_source)
    finally:
        _purge(db, owner)
        db.close()
