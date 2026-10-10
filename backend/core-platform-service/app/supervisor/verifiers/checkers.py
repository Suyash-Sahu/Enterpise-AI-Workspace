"""
Phase 29: Type-specific per-step verifiers.

Each verifier is mechanical and cheap -- no LLM judge, no network call.
They check structural invariants appropriate to each agent output type:

  - RowSetVerifier         -> database_query / database_report
  - EvidenceVerifier       -> rag_search / rag_answer / document_summary
  - InboxVerifier          -> inbox.classify (+ future commitment extraction)
  - ScheduleVerifier       -> ScheduleView outputs (calendar views)
  - ReconciliationVerifier -> Reconciliation outputs (cross-source merge)
  - DraftVerifier          -> inbox.draft_reply draft outputs

Every checker validates the shape its ExecutionHandler actually returns
(app/execution/contracts.py), NOT an idealized one:

  - Handlers wrap the agent output under a "result" key; the dispatcher
    unwraps that envelope before calling these verifiers, so `output` here
    is the inner payload (e.g. DatabaseResult.model_dump() for
    database_query, AnswerResponse.model_dump() for rag_answer,
    InboxFindings-derived {"classifications", "counts"} for inbox.classify).

An UNVERIFIED report is returned only when there is genuinely nothing to
check (empty result, no sources to verify against, no inputs to trace
against). FAILED means a specific check fired and is named in `failures`.
PASSED means every applicable check cleared.

`evidence` is accepted for StepVerifier-protocol compatibility and for
future explicit-citation flows (Phase 30 attribution); today the
supervisor passes [] and the verifiers work from the output's own ids,
which are the only mechanical ground truth available at this layer.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from app.supervisor.verifier import VerificationReport


# ── helpers ──────────────────────────────────────────────────────────────────

def _passed(checks: dict[str, Any]) -> VerificationReport:
    return VerificationReport(status="PASSED", confidence=1.0, checks=checks, failures=[])


def _failed(checks: dict[str, Any], failures: list[str]) -> VerificationReport:
    confidence = max(0.0, 1.0 - 0.35 * len(failures))
    return VerificationReport(status="FAILED", confidence=confidence, checks=checks, failures=failures)


def _unverified(reason: str) -> VerificationReport:
    return VerificationReport(
        status="UNVERIFIED", confidence=0.5,
        checks={"reason": reason}, failures=[],
    )


def _as_dt(value: Any) -> Optional[datetime]:
    """
    Best-effort parse of a calendar timestamp: datetime passthrough, epoch
    int/float, or ISO-8601 string (with trailing Z). None when unparseable --
    callers skip the affected check rather than guessing.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _event_times(event: dict[str, Any]) -> tuple[Optional[datetime], Optional[datetime]]:
    """
    Calendar events carry Google-style nested start/end objects:
    {"dateTime": "..."} (timed) or {"date": "..."} (all-day). Mirrors
    app/agents/calendar_agent.py::_event_bounds, with "date" handled too so
    an all-day block still counts as a busy interval for the free-block
    check when both sides parse.
    """
    def side(key: str) -> Optional[datetime]:
        raw = event.get(key)
        if not isinstance(raw, dict):
            return _as_dt(raw)
        return _as_dt(raw.get("dateTime")) or _as_dt(raw.get("date"))

    return side("start"), side("end")


def _overlaps(a: tuple[Optional[datetime], Optional[datetime]],
              b: tuple[Optional[datetime], Optional[datetime]]) -> Optional[bool]:
    """True/False when both intervals parse; None when either is unparseable."""
    a_start, a_end = a
    b_start, b_end = b
    if None in (a_start, a_end, b_start, b_end):
        return None
    return a_start < b_end and b_start < a_end  # type: ignore[return-value]


# ── RowSet verifier (database_query / database_report) ───────────────────────

class RowSetVerifier:
    """
    Checks the DatabaseResult payload database_query/database_report return:
    1. The executed SQL carries an owner predicate (the "owner_id" scoping
       column appears in the statement). For database_report this is
       guaranteed upstream by SQLValidator's require_owner_scope AST gate;
       for interactive database_query it is prompt-enforced only, which is
       exactly why it is re-checked here mechanically.
    2. The reported row_count equals len(rows).
    3. No row carries an explicit owner_id outside the run's owner scope.
    """

    def verify(
        self,
        inputs: dict[str, Any],
        output: dict[str, Any],
        evidence: list[str],
        owner_id: Optional[str] = None,
    ) -> VerificationReport:
        if not isinstance(output, dict):
            return _unverified("output is not a dict")

        checks: dict[str, Any] = {}
        failures: list[str] = []

        sql = str(output.get("sql") or "")
        rows = output.get("rows") if isinstance(output.get("rows"), list) else []
        reported_count = output.get("row_count")

        # 1. Owner predicate present in the executed SQL.
        if sql:
            has_predicate = "owner_id" in sql.lower()
            checks["owner_predicate_present"] = has_predicate
            if not has_predicate:
                failures.append(
                    "Executed SQL does not contain an owner_id predicate; "
                    "rows may span tenants."
                )
        else:
            checks["owner_predicate_present"] = None
            failures.append("Database step returned no SQL to verify.")

        # 2. Reported count matches the rows actually returned.
        if reported_count is not None and rows is not None:
            count_ok = reported_count == len(rows)
            checks["row_count_consistent"] = count_ok
            if not count_ok:
                failures.append(
                    f"Reported row_count={reported_count} does not match "
                    f"actual rows={len(rows)}."
                )
        else:
            checks["row_count_consistent"] = None

        # 3. No row outside the declared owner scope. Rows that do not carry
        #    an owner_id column are not evidence of a violation (most
        #    projections omit it); an explicit foreign owner_id is.
        if owner_id and rows:
            out_of_scope = [
                str(r.get("owner_id"))
                for r in rows
                if isinstance(r, dict)
                and r.get("owner_id") is not None
                and str(r.get("owner_id")) != str(owner_id)
            ]
            checks["rows_in_owner_scope"] = len(out_of_scope) == 0
            if out_of_scope:
                failures.append(
                    f"{len(out_of_scope)} row(s) carry an owner_id outside "
                    f"owner '{owner_id}'s scope."
                )
        else:
            checks["rows_in_owner_scope"] = None

        if failures:
            return _failed(checks, failures)
        return _passed(checks)


# ── Evidence verifier (rag_search / rag_answer / document_summary) ───────────

class EvidenceVerifier:
    """
    Checks RAG outputs against their real shapes:

    - rag_answer returns AnswerResponse.dump(): {"answer", "citations",
      "citations_count", ...}. A grounded answer must cite at least one
      chunk; every citation must carry a chunk_id and non-empty text; the
      reported citations_count must match the citations actually present;
      any explicitly-declared quoted spans (output["cited_spans"], or
      `evidence` entries of the form "chunk_id::span") must appear verbatim
      in the cited chunk's text.
    - rag_search returns {"results": [CitationResult...]}. Search may
      legitimately return zero results, so emptiness is UNVERIFIED, not
      FAILED -- the checks apply only to what was returned.
    """

    def verify(
        self,
        inputs: dict[str, Any],
        output: dict[str, Any],
        evidence: list[str],
        owner_id: Optional[str] = None,
    ) -> VerificationReport:
        if not isinstance(output, dict):
            return _unverified("output is not a dict")

        if "citations" in output:
            sources = output.get("citations") or []
        elif isinstance(output.get("results"), list):
            sources = output.get("results") or []
        else:
            sources = []

        if not sources:
            # A grounded *answer* with zero citations is unsupported output,
            # not an unverifiable one; a *search* with zero hits is a
            # legitimate empty result.
            if "answer" in output:
                return _failed(
                    {"has_citations": False},
                    ["Grounded answer was returned with zero citations; "
                     "the claim has no retrievable support."],
                )
            return _unverified("no citations/results in output to verify")

        checks: dict[str, Any] = {}
        failures: list[str] = []

        # 1. Every citation carries an id and readable text.
        bad_ids = [
            i for i, s in enumerate(sources)
            if not isinstance(s, dict) or not str(s.get("chunk_id") or "").strip()
        ]
        checks["all_citations_have_chunk_ids"] = len(bad_ids) == 0
        if bad_ids:
            failures.append(f"Citation(s) at index(es) {bad_ids} have no chunk_id.")

        bad_text = [
            i for i, s in enumerate(sources)
            if isinstance(s, dict) and not str(s.get("text") or "").strip()
        ]
        checks["all_citations_have_text"] = len(bad_text) == 0
        if bad_text:
            failures.append(f"Citation(s) at index(es) {bad_text} have no text; "
                            "their quoted span cannot be verified.")

        source_texts = {
            str(s.get("chunk_id")): str(s.get("text") or "")
            for s in sources
            if isinstance(s, dict) and s.get("chunk_id")
        }

        # 2. Reported citations_count matches the citations present.
        if "citations_count" in output and output.get("citations_count") is not None:
            count_ok = output.get("citations_count") == len(sources)
            checks["citations_count_consistent"] = count_ok
            if not count_ok:
                failures.append(
                    f"Reported citations_count={output.get('citations_count')} "
                    f"does not match actual citations={len(sources)}."
                )
        else:
            checks["citations_count_consistent"] = None

        # 3. Explicit quoted spans must appear verbatim in the cited chunk.
        #    Two input channels: output["cited_spans"] = [{"chunk_id", "span"}]
        #    and evidence entries shaped "chunk_id::span".
        spans: list[tuple[str, str]] = [
            (str(sp.get("chunk_id") or ""), str(sp.get("span") or ""))
            for sp in (output.get("cited_spans") or [])
            if isinstance(sp, dict)
        ]
        for entry in evidence or []:
            if isinstance(entry, str) and "::" in entry:
                cid, _, span = entry.partition("::")
                if cid and span:
                    spans.append((cid, span))

        bad_spans = [
            cid for cid, span in spans
            if cid in source_texts and span not in source_texts[cid]
        ]
        missing_span_ids = [cid for cid, _ in spans if cid not in source_texts]
        checks["cited_spans_present_in_chunks"] = len(bad_spans) == 0
        checks["all_span_chunk_ids_exist"] = len(missing_span_ids) == 0
        if bad_spans:
            failures.append(
                f"Quoted span not found in the text of chunk(s): {sorted(set(bad_spans))}."
            )
        if missing_span_ids:
            failures.append(
                f"Span cited against chunk id(s) not in the retrieved set: "
                f"{sorted(set(missing_span_ids))}."
            )

        if failures:
            return _failed(checks, failures)
        return _passed(checks)


# ── Inbox verifier (inbox.classify; commitment extraction from Phase 33) ─────

class InboxVerifier:
    """
    Checks inbox triage output:

    - Today's real shape (InboxClassifyHandler): {"classifications": [...],
      "counts": {...}} where each classification is
      {"id", "subject", "from", "label", "reason"}. Mechanical checks: every
      classification cites a message id from the fetched set (when the
      fetched set is visible in `inputs.messages`), every label is one of
      the four triage labels, and the counts summary agrees with the
      classifications actually returned.
    - Phase 33 will add {"extracted_commitments": [...]}; a commitment must
      cite a message id present in the fetched set -- checked the same way.
    """

    # Mirrors app/agents/inbox_agent.py::LABELS; imported lazily below so this
    # module stays importable without the runtime/LLM dependency chain in
    # contexts that only need the pure checkers.
    _LABELS = frozenset({"urgent", "needs_reply", "fyi", "spam"})

    def verify(
        self,
        inputs: dict[str, Any],
        output: dict[str, Any],
        evidence: list[str],
        owner_id: Optional[str] = None,
    ) -> VerificationReport:
        if not isinstance(output, dict):
            return _unverified("output is not a dict")

        messages = inputs.get("messages") if isinstance(inputs, dict) else None
        real_ids: Optional[set[str]] = None
        if isinstance(messages, list) and messages:
            real_ids = {
                str(m.get("id"))
                for m in messages
                if isinstance(m, dict) and m.get("id") is not None
            }

        commitments = output.get("extracted_commitments") or output.get("commitments")
        if commitments:
            return self._verify_commitments(commitments, real_ids)

        classifications = output.get("classifications")
        if not classifications:
            return _unverified("no classifications or commitments in output")

        checks: dict[str, Any] = {}
        failures: list[str] = []

        # 1. Every classification cites a message id from the fetched set.
        if real_ids:
            fabricated = [
                str(c.get("id")) for c in classifications
                if isinstance(c, dict) and str(c.get("id")) not in real_ids
            ]
            checks["all_classifications_cite_fetched_ids"] = len(fabricated) == 0
            if fabricated:
                failures.append(
                    f"Classification(s) cite message id(s) not in the fetched "
                    f"set: {sorted(set(fabricated))}."
                )
        else:
            # Server-side fetch (messages=None): the fetched set is not
            # visible at this layer, so identity cannot be checked -- but
            # every classification must still cite *some* id.
            no_id = [
                i for i, c in enumerate(classifications)
                if not isinstance(c, dict) or c.get("id") is None
                or not str(c.get("id")).strip()
            ]
            checks["all_classifications_cite_fetched_ids"] = len(no_id) == 0
            if no_id:
                failures.append(
                    f"Classification(s) at index(es) {no_id} carry no message id."
                )

        # 2. Labels are from the fixed triage vocabulary.
        bad_labels = [
            str(c.get("label")) for c in classifications
            if isinstance(c, dict) and str(c.get("label") or "").lower() not in self._LABELS
        ]
        checks["labels_in_vocabulary"] = len(bad_labels) == 0
        if bad_labels:
            failures.append(
                f"Classification label(s) outside the triage vocabulary: "
                f"{sorted(set(bad_labels))}."
            )

        # 3. Counts summary agrees with the classifications.
        counts = output.get("counts")
        if isinstance(counts, dict):
            recomputed: dict[str, int] = {}
            for c in classifications:
                if isinstance(c, dict):
                    label = str(c.get("label") or "").lower()
                    recomputed[label] = recomputed.get(label, 0) + 1
            counts_ok = {
                k: v for k, v in counts.items() if v
            } == {k: v for k, v in recomputed.items() if v}
            checks["counts_consistent"] = counts_ok
            if not counts_ok:
                failures.append(
                    f"Reported counts {counts} disagree with the "
                    f"classifications returned ({recomputed})."
                )
        else:
            checks["counts_consistent"] = None

        if failures:
            return _failed(checks, failures)
        return _passed(checks)

    def _verify_commitments(
        self,
        commitments: list[Any],
        real_ids: Optional[set[str]],
    ) -> VerificationReport:
        checks: dict[str, Any] = {}
        failures: list[str] = []

        if real_ids:
            fabricated = [
                str(c.get("message_id") or c.get("source_id"))
                for c in commitments
                if isinstance(c, dict)
                and str(c.get("message_id") or c.get("source_id") or "") not in real_ids
            ]
            checks["all_commitments_cite_fetched_ids"] = len(fabricated) == 0
            if fabricated:
                failures.append(
                    f"Commitment(s) cite message id(s) not in the fetched set: "
                    f"{sorted(set(fabricated))}."
                )
        else:
            no_id = [
                i for i, c in enumerate(commitments)
                if not isinstance(c, dict)
                or not str(c.get("message_id") or c.get("source_id") or "").strip()
            ]
            checks["all_commitments_cite_fetched_ids"] = len(no_id) == 0
            if no_id:
                failures.append(
                    f"Commitment(s) at index(es) {no_id} cite no message id."
                )

        if failures:
            return _failed(checks, failures)
        return _passed(checks)


# ── Schedule verifier (ScheduleView outputs) ─────────────────────────────────

class ScheduleVerifier:
    """
    Checks a ScheduleView payload (app/agents/calendar_agent.py):
    1. Every reported conflict is a genuine overlap of two events that both
       exist in the returned event list -- no invented conflicts.
    2. Every reported free block is disjoint from the busy events.

    Real conflicts are {"event_a": <summary>, "event_b": <summary>} strings;
    intervals are recovered from the events list by summary. When either
    side's timestamps are unparseable the interval check is skipped (not
    failed) -- an invented-summary conflict still fails check 1.
    """

    def verify(
        self,
        inputs: dict[str, Any],
        output: dict[str, Any],
        evidence: list[str],
        owner_id: Optional[str] = None,
    ) -> VerificationReport:
        if not isinstance(output, dict):
            return _unverified("output is not a dict")

        events = output.get("events") if isinstance(output.get("events"), list) else []
        conflicts = output.get("conflicts") if isinstance(output.get("conflicts"), list) else []
        free_blocks = output.get("free_blocks") if isinstance(output.get("free_blocks"), list) else []

        if not conflicts and not free_blocks:
            return _unverified("no conflicts or free blocks in output to verify")

        checks: dict[str, Any] = {}
        failures: list[str] = []

        by_summary: dict[str, list[tuple[Optional[datetime], Optional[datetime]]]] = {}
        for event in events:
            if isinstance(event, dict) and event.get("summary"):
                by_summary.setdefault(str(event["summary"]), []).append(_event_times(event))

        # 1. Conflicts: both sides exist, and genuinely overlap.
        invented: list[str] = []
        false_conflicts: list[str] = []
        unparseable = 0
        for conflict in conflicts:
            if not isinstance(conflict, dict):
                invented.append(str(conflict))
                continue
            a_name = str(conflict.get("event_a") or "")
            b_name = str(conflict.get("event_b") or "")
            if a_name not in by_summary or b_name not in by_summary:
                invented.append(f"{a_name!r}/{b_name!r}")
                continue
            overlaps = [
                _overlaps(a, b)
                for a in by_summary[a_name]
                for b in by_summary[b_name]
            ]
            if all(o is None for o in overlaps):
                unparseable += 1
                continue
            if not any(o for o in overlaps if o is not None):
                false_conflicts.append(f"{a_name!r} vs {b_name!r}")

        checks["conflicts_reference_returned_events"] = len(invented) == 0
        checks["conflicts_are_genuine_overlaps"] = len(false_conflicts) == 0
        if invented:
            failures.append(
                f"Conflict(s) reference event(s) not in the returned schedule: {invented}."
            )
        if false_conflicts:
            failures.append(
                f"Reported conflict(s) are not actual overlaps: {false_conflicts}."
            )
        if unparseable:
            checks["conflict_intervals_unparseable"] = unparseable

        # 2. Free blocks must not intersect busy events.
        false_frees: list[str] = []
        free_unparseable = 0
        for free in free_blocks:
            if not isinstance(free, dict):
                false_frees.append(str(free))
                continue
            f_start = _as_dt(free.get("start"))
            f_end = _as_dt(free.get("end"))
            if f_start is None or f_end is None:
                free_unparseable += 1
                continue
            busy = [_event_times(e) for e in events if isinstance(e, dict)]
            hit = next(
                (True for b in busy if _overlaps((f_start, f_end), b) is True),
                False,
            )
            if hit:
                false_frees.append(str(free.get("summary") or free.get("id") or "?"))

        checks["free_blocks_do_not_intersect_busy"] = len(false_frees) == 0
        if false_frees:
            failures.append(
                f"Free block(s) overlap busy events: {false_frees}."
            )
        if free_unparseable:
            checks["free_block_intervals_unparseable"] = free_unparseable

        if failures:
            return _failed(checks, failures)
        return _passed(checks)


# ── Reconciliation verifier ──────────────────────────────────────────────────

class ReconciliationVerifier:
    """
    Checks a Reconciliation payload (app/agents/reconciler_agent.py):
    every merged item traces to at least one source item in the declared
    inputs -- its "sources" are non-empty, each cited source exists among
    the input items' sources, and its key exists among the input items' keys.
    No invented items.

    `inputs.items` is the ReconcileInput-shaped list the caller passed in
    ([{"key", "value", "source"}...]). When the inputs carry no items there
    is nothing to trace against and the report is UNVERIFIED, not PASSED --
    an unverifiable merge must never be scored as a verified one.
    """

    def verify(
        self,
        inputs: dict[str, Any],
        output: dict[str, Any],
        evidence: list[str],
        owner_id: Optional[str] = None,
    ) -> VerificationReport:
        if not isinstance(output, dict):
            return _unverified("output is not a dict")

        merged = output.get("merged") if isinstance(output.get("merged"), list) else []
        if not merged:
            return _unverified("no merged items in output")

        input_items = inputs.get("items") if isinstance(inputs, dict) else None
        if not isinstance(input_items, list) or not input_items:
            return _unverified("no source items in inputs to trace the merge against")

        real_sources = {
            str(i.get("source"))
            for i in input_items
            if isinstance(i, dict) and i.get("source") is not None
        }
        real_keys = {
            str(i.get("key")).strip().lower()
            for i in input_items
            if isinstance(i, dict) and i.get("key") is not None
        }

        checks: dict[str, Any] = {}
        failures: list[str] = []

        no_source: list[str] = []
        unknown_sources: list[str] = []
        unknown_keys: list[str] = []

        for item in merged:
            if not isinstance(item, dict):
                no_source.append(str(item))
                continue
            item_key = str(item.get("key") or "?")
            sources_cited = item.get("sources") or []
            if not sources_cited:
                no_source.append(item_key)
                continue
            for sid in sources_cited:
                if str(sid) not in real_sources:
                    unknown_sources.append(str(sid))
            if item_key.strip().lower() not in real_keys:
                unknown_keys.append(item_key)

        checks["no_invented_items"] = not (no_source or unknown_keys)
        checks["all_cited_sources_exist"] = len(unknown_sources) == 0
        if no_source:
            failures.append(
                f"Merged item(s) cite no source item -- may be invented: {no_source}."
            )
        if unknown_keys:
            failures.append(
                f"Merged item(s) have keys absent from the input items: {unknown_keys}."
            )
        if unknown_sources:
            failures.append(
                f"Merged item(s) cite source(s) not among the input items: "
                f"{sorted(set(unknown_sources))}."
            )

        if failures:
            return _failed(checks, failures)
        return _passed(checks)


# ── Draft verifier (inbox.draft_reply) ───────────────────────────────────────

class DraftVerifier:
    """
    Checks a reply-draft payload (InboxDraftReplyHandler /
    InboxAgent.draft_reply): {"to", "subject", "body", "sent": False,
    "send_capability": "gmail.send"}.

    1. No fabricated recipient: "to" must be the original message's From
       header -- the only recipient the agent is allowed to derive (a body
       asking to "reply to attacker@evil.com" must not be able to redirect
       the draft).
    2. The draft must not claim it was sent ("sent": True would be a false
       side-effect claim; sending is the separate approval-gated
       gmail.send capability).
    3. No fabricated email addresses in the body: addresses appearing in
       the body must come from the declared inputs (original sender /
       original recipients / original body), not from anywhere else.
    """

    _EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+\-]+@[a-zA-Z0-9\-]+\.[a-zA-Z]{2,}")

    def verify(
        self,
        inputs: dict[str, Any],
        output: dict[str, Any],
        evidence: list[str],
        owner_id: Optional[str] = None,
    ) -> VerificationReport:
        if not isinstance(output, dict):
            return _unverified("output is not a dict")

        body = str(output.get("body") or "")
        to = str(output.get("to") or "")
        if not body and not to:
            return _unverified("draft has neither recipient nor body to verify")

        message = inputs.get("message") if isinstance(inputs, dict) else None
        checks: dict[str, Any] = {}
        failures: list[str] = []

        # 1. Recipient is the original sender.
        if isinstance(message, dict) and message.get("from"):
            expected_to = str(message["from"])
            checks["recipient_from_original_message"] = to == expected_to
            if to != expected_to:
                failures.append(
                    f"Draft recipient {to!r} is not the original message's "
                    f"sender {expected_to!r}; recipient may be fabricated."
                )
        elif not to:
            checks["recipient_from_original_message"] = None
            failures.append("Draft carries no recipient.")
        else:
            # Message fetched server-side by id: the recipient's provenance
            # is not visible here and cannot be mechanically checked.
            checks["recipient_from_original_message"] = None

        # 2. A draft is not a send.
        sent_claimed = output.get("sent")
        checks["draft_not_sent"] = sent_claimed is not True
        if sent_claimed is True:
            failures.append(
                "Draft output claims sent=True; sending is a separate, "
                "approval-gated capability and must never be claimed here."
            )

        # 3. Addresses in the body must come from the declared inputs.
        if isinstance(message, dict):
            allowed = set(self._EMAIL_RE.findall(str(message)))
            allowed |= set(self._EMAIL_RE.findall(str(inputs.get("instructions") or "")))
            body_addrs = set(self._EMAIL_RE.findall(body))
            fabricated = {a.lower() for a in body_addrs} - {a.lower() for a in allowed}
            checks["no_fabricated_addresses_in_body"] = len(fabricated) == 0
            if fabricated:
                failures.append(
                    f"Draft body contain(s) email address(es) absent from the "
                    f"declared inputs: {sorted(fabricated)}."
                )
        else:
            checks["no_fabricated_addresses_in_body"] = None

        if failures:
            return _failed(checks, failures)
        return _passed(checks)


# ── Instances ─────────────────────────────────────────────────────────────────

rowset_verifier = RowSetVerifier()
evidence_verifier = EvidenceVerifier()
inbox_verifier = InboxVerifier()
schedule_verifier = ScheduleVerifier()
reconciliation_verifier = ReconciliationVerifier()
draft_verifier = DraftVerifier()

__all__ = [
    "RowSetVerifier", "EvidenceVerifier", "InboxVerifier",
    "ScheduleVerifier", "ReconciliationVerifier", "DraftVerifier",
    "rowset_verifier", "evidence_verifier", "inbox_verifier",
    "schedule_verifier", "reconciliation_verifier", "draft_verifier",
]
