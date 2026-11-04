"""
Tests for Commitment Intelligence V2:
- Run lifecycle, stages, and execution recovery
- Date parser and deadline intelligence
- Ownership and directions (owed_by_me, owed_to_me, mutual)
- Status lifecycle (pending, at_risk, overdue, completed, dismissed, reopened)
- Evidence verification
- AI follow-up draft generation
- WorkGraph task proposal creation
- Analytics and audit event history
"""
from datetime import datetime, timedelta, timezone
from app.db.database import Base, SessionLocal, engine
from app.models.commitment import Commitment
from app.models.commitment_run import CommitmentRun
from app.models.work_ai import AiProposal
from app.services.commitment_service import commitment_service
from app.services.commitment_run_service import commitment_run_service
from app.utils.date_parser import parse_deadline


def _clean_db(db, owner_id: str):
    db.query(Commitment).filter(Commitment.owner_id == owner_id).delete()
    db.query(CommitmentRun).filter(CommitmentRun.owner_id == owner_id).delete()
    db.query(AiProposal).filter(AiProposal.owner_id == owner_id).delete()
    db.commit()


def test_date_parser_natural_language():
    p_tomorrow = parse_deadline("tomorrow")
    assert p_tomorrow.normalized_dt is not None
    assert p_tomorrow.confidence >= 0.9

    p_eow = parse_deadline("end of this week")
    assert p_eow.normalized_dt is not None

    p_days = parse_deadline("within 3 days")
    assert p_days.normalized_dt is not None

    p_explicit = parse_deadline("2026-12-15")
    assert p_explicit.normalized_dt is not None
    assert p_explicit.normalized_dt.year == 2026
    assert p_explicit.normalized_dt.month == 12
    assert p_explicit.normalized_dt.day == 15


def test_run_creation_and_stages(test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        _clean_db(db, owner)
        run = commitment_run_service.create_run(db, owner_id=owner, run_type="scan")
        assert run.id.startswith("crun_")
        assert run.status == "queued"
        assert len(run.stages) == 8
        assert run.stages[0].stage_name == "initialize_scan"
        assert run.stages[-1].stage_name == "finalize_results"

        # Check retrieval
        fetched = commitment_run_service.get_run(db, run.id, owner)
        assert fetched is not None
        assert fetched.id == run.id

        # Cancel run
        cancelled = commitment_run_service.cancel_run(db, run.id, owner)
        assert cancelled.status == "cancelled"
        assert cancelled.cancel_requested is True
    finally:
        _clean_db(db, owner)
        db.close()


def test_bidirectional_commitment_tracking_and_crud(test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        _clean_db(db, owner)

        # 1. Create Owed by Me
        c1 = commitment_service.create_commitment(
            db=db,
            owner_id=owner,
            description="Send architectural deck",
            responsible_party="Current User",
            counterparty="VP of Eng",
            direction="owed_by_me",
            due_date="tomorrow",
            priority="high",
            evidence="I promised to send the deck tomorrow morning.",
        )
        assert c1.direction == "owed_by_me"
        assert c1.status in ("pending", "at_risk")
        assert c1.counterparty == "VP of Eng"
        assert c1.normalized_due_date is not None

        # 2. Create Owed to Me
        c2 = commitment_service.create_commitment(
            db=db,
            owner_id=owner,
            description="Provide API access keys",
            responsible_party="Partner Tech Lead",
            counterparty="Current User",
            direction="owed_to_me",
            due_date="next Monday",
            priority="medium",
            evidence="We will generate and send your API keys by next Monday.",
        )
        assert c2.direction == "owed_to_me"

        # 3. Read & filter
        by_me = commitment_service.list_commitments(db, owner, direction="owed_by_me")
        assert len(by_me) == 1
        assert by_me[0].id == c1.id

        to_me = commitment_service.list_commitments(db, owner, direction="owed_to_me")
        assert len(to_me) == 1
        assert to_me[0].id == c2.id

        # 4. Complete, dismiss, reopen
        completed = commitment_service.complete_commitment(db, c1.id, owner)
        assert completed.status == "completed"
        assert completed.verification_status == "verified"

        dismissed = commitment_service.dismiss_commitment(db, c2.id, owner)
        assert dismissed.status == "dismissed"

        reopened = commitment_service.reopen_commitment(db, c2.id, owner)
        assert reopened.status == "pending"

        # 5. Check audit events
        events = commitment_service.get_commitment(db, c1.id, owner)
        assert events is not None
    finally:
        _clean_db(db, owner)
        db.close()


def test_verification_and_follow_up_and_proposals(test_user):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    owner = str(test_user.id)
    try:
        _clean_db(db, owner)

        c = commitment_service.create_commitment(
            db=db,
            owner_id=owner,
            description="Deliver product roadmap update",
            responsible_party="Alice Smith",
            counterparty="Current User",
            direction="owed_to_me",
            due_date="yesterday",
            priority="high",
        )

        # Verification
        verified = commitment_service.verify_commitment(
            db,
            commitment_id=c.id,
            owner_id=owner,
            verification_status="verified",
            evidence="Sent email with 'Roadmap v2 attached'",
            reasoning="Deliverable email confirmed received",
        )
        assert verified.verification_status == "verified"
        assert verified.status == "completed"

        # Follow-up generation
        c2 = commitment_service.create_commitment(
            db=db,
            owner_id=owner,
            description="Review PR #45",
            responsible_party="Bob Jones",
            counterparty="Current User",
            direction="owed_to_me",
            due_date="2026-11-01",
        )
        draft = commitment_service.generate_follow_up(db, c2.id, owner)
        assert "Bob Jones" in draft["body"]
        assert "Review PR #45" in draft["subject"] or "Review PR #45" in draft["body"]

        # WorkGraph task proposal
        proposal = commitment_service.propose_task(db, c2.id, owner)
        assert proposal["status"] == "created"
        assert "proposal_id" in proposal

        # Check duplicate proposal protection
        dup = commitment_service.propose_task(db, c2.id, owner)
        assert dup["status"] == "already_exists"

        # Check stats & analytics
        stats = commitment_service.get_stats(db, owner)
        assert stats["total"] >= 2
        analytics = commitment_service.get_analytics(db, owner)
        assert "direction_distribution" in analytics
        assert "status_distribution" in analytics
    finally:
        _clean_db(db, owner)
        db.close()

