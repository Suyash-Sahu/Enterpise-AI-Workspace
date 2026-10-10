"""
Phase 29: unit tests for the type-specific per-step verifiers.

One positive and one negative case per verifier type. The negative case
names the specific failed check and its failure message.

These exercise the *checker* layer directly (app/supervisor/verifiers/
checkers.py) against the exact output shapes the ExecutionHandlers return
(app/execution/contracts.py) -- the same shapes the dispatcher unwraps in
production.
"""
import pytest
from datetime import datetime, timedelta, timezone

from app.supervisor.verifier import VerificationReport
from app.supervisor.verifiers.checkers import (
    draft_verifier,
    evidence_verifier,
    inbox_verifier,
    reconciliation_verifier,
    rowset_verifier,
    schedule_verifier,
)


def assert_failed(report: VerificationReport, failed_check: str, fragment: str) -> None:
    """Negative-case helper: FAILED status, the named check False, message fragment present."""
    assert report.status == "FAILED"
    assert report.checks.get(failed_check) is False, report.checks
    assert any(fragment in f for f in report.failures), report.failures


# ── RowSetVerifier (database_query / database_report) ────────────────────────

def test_rowset_positive():
    output = {
        "question": "How many documents?",
        "sql": "SELECT source, chunk_count FROM ingested_documents WHERE owner_id = :owner_id",
        "rows": [{"source": "a.pdf", "chunk_count": 3}, {"source": "b.pdf", "chunk_count": 1}],
        "row_count": 2,
        "columns": ["source", "chunk_count"],
    }
    report = rowset_verifier.verify(inputs={}, output=output, evidence=[], owner_id="42")
    assert report.status == "PASSED", report.failures
    assert report.checks["owner_predicate_present"] is True
    assert report.checks["row_count_consistent"] is True
    # Rows carry no owner_id column at all: no evidence of a violation.
    assert report.checks["rows_in_owner_scope"] is True


def test_rowset_negative_missing_owner_predicate():
    output = {
        "sql": "SELECT source, chunk_count FROM ingested_documents",
        "rows": [],
        "row_count": 0,
    }
    report = rowset_verifier.verify(inputs={}, output=output, evidence=[], owner_id="42")
    assert_failed(
        report,
        "owner_predicate_present",
        "does not contain an owner_id predicate",
    )


def test_rowset_negative_row_count_mismatch():
    output = {
        "sql": "SELECT source FROM ingested_documents WHERE owner_id = :owner_id",
        "rows": [{"source": "a.pdf"}],
        "row_count": 5,
    }
    report = rowset_verifier.verify(inputs={}, output=output, evidence=[], owner_id="42")
    assert_failed(report, "row_count_consistent", "does not match actual rows=1")


def test_rowset_negative_row_outside_owner_scope():
    output = {
        "sql": "SELECT owner_id, source FROM ingested_documents WHERE owner_id = :owner_id",
        "rows": [{"owner_id": "999", "source": "leaked.pdf"}],
        "row_count": 1,
    }
    report = rowset_verifier.verify(inputs={}, output=output, evidence=[], owner_id="42")
    assert_failed(report, "rows_in_owner_scope", "outside owner '42's scope")


# ── EvidenceVerifier (rag_search / rag_answer) ───────────────────────────────

def _citation(chunk_id: str, text: str) -> dict:
    return {
        "chunk_id": chunk_id,
        "file_id": "f1",
        "source": "doc.pdf",
        "owner_id": "42",
        "page": 1,
        "chunk_index": 0,
        "text": text,
        "score": 0.9,
        "vector_score": 0.8,
        "keyword_score": 0.7,
        "rerank_score": 0.6,
    }


def test_evidence_positive_rag_answer():
    output = {
        "answer": "Hybrid search combines vector and keyword scores.",
        "citations": [_citation("c1", "Hybrid search combines vector and keyword scores with RRF.")],
        "citations_count": 1,
    }
    report = evidence_verifier.verify(inputs={}, output=output, evidence=[])
    assert report.status == "PASSED", report.failures


def test_evidence_negative_quoted_span_not_in_chunk():
    output = {
        "answer": "The system uses quantum retrieval.",
        "citations": [_citation("c1", "Hybrid search combines vector and keyword scores with RRF.")],
        "citations_count": 1,
        "cited_spans": [{"chunk_id": "c1", "span": "quantum retrieval"}],
    }
    report = evidence_verifier.verify(inputs={}, output=output, evidence=[])
    assert_failed(report, "cited_spans_present_in_chunks", "Quoted span not found")


def test_evidence_negative_citation_count_mismatch():
    output = {
        "answer": "Something.",
        "citations": [_citation("c1", "text one")],
        "citations_count": 3,
    }
    report = evidence_verifier.verify(inputs={}, output=output, evidence=[])
    assert_failed(report, "citations_count_consistent", "citations_count=3")


def test_evidence_negative_grounded_answer_without_citations():
    output = {"answer": "A confident-sounding claim.", "citations": [], "citations_count": 0}
    report = evidence_verifier.verify(inputs={}, output=output, evidence=[])
    assert_failed(report, "has_citations", "zero citations")


def test_evidence_positive_rag_search_empty_results_is_unverified():
    # A search with zero hits is legitimate; it is UNVERIFIED, never FAILED.
    report = evidence_verifier.verify(inputs={}, output={"results": []}, evidence=[])
    assert report.status == "UNVERIFIED"


# ── InboxVerifier (inbox.classify) ───────────────────────────────────────────

def _classification(mid: str, label: str = "fyi") -> dict:
    return {"id": mid, "subject": "s", "from": "sender@example.com", "label": label, "reason": "r"}


def test_inbox_positive():
    inputs = {"messages": [{"id": "m1"}, {"id": "m2"}]}
    output = {
        "classifications": [_classification("m1", "urgent"), _classification("m2", "needs_reply")],
        "counts": {"urgent": 1, "needs_reply": 1},
    }
    report = inbox_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert report.status == "PASSED", report.failures


def test_inbox_negative_fabricated_message_id():
    inputs = {"messages": [{"id": "m1"}]}
    output = {
        "classifications": [_classification("m1"), _classification("ghost-msg")],
        "counts": {"fyi": 2},
    }
    report = inbox_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "all_classifications_cite_fetched_ids", "ghost-msg")


def test_inbox_negative_label_outside_vocabulary():
    inputs = {"messages": [{"id": "m1"}]}
    output = {
        "classifications": [_classification("m1", "definitely_spam_delete_it")],
        "counts": {},
    }
    report = inbox_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "labels_in_vocabulary", "outside the triage vocabulary")


def test_inbox_negative_counts_disagree_with_classifications():
    inputs = {"messages": [{"id": "m1"}, {"id": "m2"}]}
    output = {
        "classifications": [_classification("m1", "urgent"), _classification("m2", "fyi")],
        "counts": {"urgent": 2},
    }
    report = inbox_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "counts_consistent", "disagree with the classifications")


def test_inbox_positive_commitments_cite_fetched_ids():
    inputs = {"messages": [{"id": "m1"}]}
    output = {
        "extracted_commitments": [{"message_id": "m1", "commitment": "send report"}],
    }
    report = inbox_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert report.status == "PASSED", report.failures


def test_inbox_negative_commitment_cites_unfetched_id():
    inputs = {"messages": [{"id": "m1"}]}
    output = {
        "extracted_commitments": [{"message_id": "made-up", "commitment": "send report"}],
    }
    report = inbox_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "all_commitments_cite_fetched_ids", "made-up")


# ── ScheduleVerifier (ScheduleView) ──────────────────────────────────────────

def _event(summary: str, start: datetime, end: datetime) -> dict:
    return {
        "summary": summary,
        "start": {"dateTime": start.isoformat()},
        "end": {"dateTime": end.isoformat()},
    }


def test_schedule_positive():
    base = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc)
    events = [
        _event("A", base, base + timedelta(hours=1)),
        _event("B", base + timedelta(minutes=30), base + timedelta(minutes=90)),
        _event("C", base + timedelta(hours=2), base + timedelta(hours=3)),
    ]
    output = {
        "events": events,
        "conflicts": [{"event_a": "A", "event_b": "B"}],
        # The real gap between B's end (10:30) and C's start (11:00).
        "free_blocks": [{"summary": "midday gap", "start": (base + timedelta(hours=1, minutes=30)).isoformat(), "end": (base + timedelta(hours=2)).isoformat()}],
    }
    report = schedule_verifier.verify(inputs={}, output=output, evidence=[])
    assert report.status == "PASSED", report.failures


def test_schedule_negative_conflict_is_not_a_real_overlap():
    base = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc)
    events = [
        _event("A", base, base + timedelta(hours=1)),
        _event("B", base + timedelta(hours=2), base + timedelta(hours=3)),
    ]
    output = {
        "events": events,
        "conflicts": [{"event_a": "A", "event_b": "B"}],
    }
    report = schedule_verifier.verify(inputs={}, output=output, evidence=[])
    assert_failed(report, "conflicts_are_genuine_overlaps", "not actual overlaps")


def test_schedule_negative_conflict_references_unreturned_event():
    base = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc)
    events = [_event("A", base, base + timedelta(hours=1))]
    output = {
        "events": events,
        "conflicts": [{"event_a": "A", "event_b": "Ghost Meeting"}],
    }
    report = schedule_verifier.verify(inputs={}, output=output, evidence=[])
    assert_failed(report, "conflicts_reference_returned_events", "not in the returned schedule")


def test_schedule_negative_free_block_intersects_busy_event():
    base = datetime(2026, 9, 22, 9, 0, tzinfo=timezone.utc)
    events = [_event("Busy", base, base + timedelta(hours=1))]
    output = {
        "events": events,
        "free_blocks": [{"summary": "bad free", "start": base.isoformat(), "end": (base + timedelta(minutes=30)).isoformat()}],
    }
    report = schedule_verifier.verify(inputs={}, output=output, evidence=[])
    assert_failed(report, "free_blocks_do_not_intersect_busy", "overlap busy events")


# ── ReconciliationVerifier ───────────────────────────────────────────────────

def test_reconciliation_positive():
    inputs = {"items": [
        {"key": "budget", "value": 100, "source": "DataAgent"},
        {"key": "budget", "value": 100, "source": "KnowledgeAgent"},
    ]}
    output = {
        "merged": [{"key": "budget", "value": 100, "sources": ["DataAgent", "KnowledgeAgent"]}],
        "duplicates": [{"key": "budget", "value": 100, "sources": ["DataAgent", "KnowledgeAgent"]}],
        "contradictions": [],
    }
    report = reconciliation_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert report.status == "PASSED", report.failures


def test_reconciliation_negative_merged_item_without_sources():
    inputs = {"items": [{"key": "budget", "value": 100, "source": "DataAgent"}]}
    output = {
        "merged": [{"key": "budget", "value": 100, "sources": []}],
    }
    report = reconciliation_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "no_invented_items", "cite no source item")


def test_reconciliation_negative_invented_key():
    inputs = {"items": [{"key": "budget", "value": 100, "source": "DataAgent"}]}
    output = {
        "merged": [{"key": "headcount", "value": 7, "sources": ["DataAgent"]}],
    }
    report = reconciliation_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "no_invented_items", "keys absent from the input items")


def test_reconciliation_negative_unknown_source():
    inputs = {"items": [{"key": "budget", "value": 100, "source": "DataAgent"}]}
    output = {
        "merged": [{"key": "budget", "value": 100, "sources": ["GhostAgent"]}],
    }
    report = reconciliation_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "all_cited_sources_exist", "GhostAgent")


def test_reconciliation_no_inputs_is_unverified_not_passed():
    report = reconciliation_verifier.verify(inputs={}, output={"merged": [{"key": "k", "sources": ["s"]}]}, evidence=[])
    assert report.status == "UNVERIFIED"


# ── DraftVerifier (inbox.draft_reply) ────────────────────────────────────────

def test_draft_positive():
    inputs = {"message": {"id": "m1", "from": "alice@example.com", "subject": "Question", "body": "Is the report ready?"}}
    output = {
        "to": "alice@example.com",
        "subject": "Re: Question",
        "body": "Hi Alice, the report will be ready tomorrow.",
        "sent": False,
        "send_capability": "gmail.send",
    }
    report = draft_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert report.status == "PASSED", report.failures


def test_draft_negative_fabricated_recipient():
    inputs = {"message": {"id": "m1", "from": "alice@example.com", "subject": "Question", "body": "Is the report ready?"}}
    output = {
        "to": "attacker@evil.com",  # must be the original sender, never model-chosen
        "subject": "Re: Question",
        "body": "Hello.",
        "sent": False,
    }
    report = draft_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "recipient_from_original_message", "may be fabricated")


def test_draft_negative_body_redirect_address():
    # The injection case: the draft body tries to redirect follow-up to a
    # third-party address that appears nowhere in the declared inputs.
    inputs = {"message": {"id": "m1", "from": "alice@example.com", "body": "Please confirm."}}
    output = {
        "to": "alice@example.com",
        "subject": "Re:",
        "body": "Confirming. If anything changes write to attacker@evil.com.",
        "sent": False,
    }
    report = draft_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "no_fabricated_addresses_in_body", "absent from the declared inputs")


def test_draft_negative_claims_sent():
    inputs = {"message": {"id": "m1", "from": "alice@example.com", "body": "Hi"}}
    output = {"to": "alice@example.com", "subject": "Re:", "body": "Done.", "sent": True}
    report = draft_verifier.verify(inputs=inputs, output=output, evidence=[])
    assert_failed(report, "draft_not_sent", "must never be claimed here")


# ── Dispatcher: envelope + mode behavior ─────────────────────────────────────

def test_dispatcher_unwraps_handler_result_envelope(monkeypatch):
    from app.core.config import settings
    from app.supervisor.verifiers.dispatcher import verify_step

    monkeypatch.setattr(settings, "VERIFICATION_MODE", "per_step")

    # DatabaseQueryHandler's real shape: DatabaseResult nested under "result".
    handler_output = {
        "result": {
            "question": "q",
            "sql": "SELECT source FROM ingested_documents WHERE owner_id = :owner_id",
            "rows": [{"source": "a"}],
            "row_count": 1,
        },
        "provider": "postgresql",
        "model": "m",
    }
    report = verify_step(
        capability="database_query",
        inputs={"question": "q"},
        output=handler_output,
        owner_id="42",
    )
    assert report.status == "PASSED", report.failures


def test_dispatcher_known_capability_passes_owner_id(monkeypatch):
    from app.core.config import settings
    from app.supervisor.verifiers.dispatcher import verify_step

    monkeypatch.setattr(settings, "VERIFICATION_MODE", "per_step")
    output = {
        "result": {
            "sql": "SELECT source FROM ingested_documents",
            "rows": [{"owner_id": "999"}],
            "row_count": 1,
        },
    }
    report = verify_step(capability="database_query", inputs={}, output=output, owner_id="42")
    assert report.status == "FAILED"
    assert report.checks["rows_in_owner_scope"] is False


def test_dispatcher_unknown_capability_is_unverified(monkeypatch):
    from app.core.config import settings
    from app.supervisor.verifiers.dispatcher import verify_step

    monkeypatch.setattr(settings, "VERIFICATION_MODE", "per_step")
    report = verify_step(capability="text_generation", inputs={}, output={"result": {"generated_text": "x"}})
    assert report.status == "UNVERIFIED"


def test_dispatcher_off_and_final_only_return_unverified(monkeypatch):
    from app.core.config import settings
    from app.supervisor.verifiers.dispatcher import verify_step

    output = {"result": {"sql": "SELECT 1", "rows": [], "row_count": 0}}
    for mode in ("off", "final_only"):
        monkeypatch.setattr(settings, "VERIFICATION_MODE", mode)
        report = verify_step(capability="database_query", inputs={}, output=output)
        assert report.status == "UNVERIFIED"
        assert report.checks == {"mode": mode}


def test_verification_mode_for_run_honors_run_toggle():
    from app.supervisor.verifiers.dispatcher import verification_mode_for_run

    class Ctx:
        verification_enabled = False

    assert verification_mode_for_run(Ctx()) == "off"


def test_verification_mode_for_run_uses_setting_when_enabled(monkeypatch):
    from app.core.config import settings
    from app.supervisor.verifiers.dispatcher import verification_mode_for_run

    class Ctx:
        verification_enabled = True

    monkeypatch.setattr(settings, "VERIFICATION_MODE", "final_only")
    assert verification_mode_for_run(Ctx()) == "final_only"
