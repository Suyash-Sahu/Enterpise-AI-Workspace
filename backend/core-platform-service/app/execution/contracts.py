from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, ClassVar, Optional
from sqlalchemy.orm import Session

from app.agents.base import AgentContext
from app.agents.knowledge_agent import knowledge_agent, KnowledgeSearchInput, KnowledgeAnswerInput
from app.agents.database_agent import data_agent, DataAgentInput
from app.agents.document_agent import document_ops_agent, DocumentSummaryHandlerInput


@dataclass
class ExecutionContext:
    owner_id: str
    execution_id: str
    request_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    timeout: float = 30.0
    execution_mode: str = "auto"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityMetadata:
    """
    What a capability handler IS, declared by the handler itself rather than
    inferred at call time -- side_effect/requires_human_approval decide
    whether an approval gate applies, and that decision must never be left to
    the LLM's own judgment about what it's allowed to do.
    """
    description: str
    risk_level: str  # "low" | "medium" | "high"
    # "read_only" | "reversible_write" | "irreversible_write" |
    # "external_communication" | "destructive"
    side_effect: str
    requires_verification: bool = True
    requires_human_approval: bool = False


class ExecutionHandler(ABC):

    # Every concrete handler must declare this. No default: an undeclared
    # metadata is a bug to catch at registration time (see TaskRegistry),
    # not a silent "assume it's safe."
    metadata: ClassVar[CapabilityMetadata]

    @abstractmethod
    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        """
        Executes capability task synchronously and returns task results including metadata.
        Must return a dict containing 'result', and optionally 'provider' and 'model'.
        """


class RAGSearchHandler(ExecutionHandler):
    metadata = CapabilityMetadata(
        description="Hybrid vector+keyword search over ingested document chunks.",
        risk_level="low",
        side_effect="read_only",
        requires_verification=False,  # returns raw chunks, not a generated claim
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        query = input_data.get("query", "")
        top_k = input_data.get("top_k", 5)
        file_id = input_data.get("file_id")

        agent_result = knowledge_agent.run(
            AgentContext(owner_id=context.owner_id, db=db, execution_mode=context.execution_mode,
                         timeout=context.timeout, request_id=context.request_id, metadata=context.metadata),
            KnowledgeSearchInput(query=query, top_k=top_k, file_id=file_id),
        )
        res = agent_result.output
        return {
            "result": {"results": [item.model_dump() for item in res]},
            "provider": "pgvector_bm25",
            "model": "hybrid_rrf",
        }


class RAGAnswerHandler(ExecutionHandler):
    metadata = CapabilityMetadata(
        description="Retrieval-grounded question answering over ingested documents.",
        risk_level="low",
        side_effect="read_only",
        requires_verification=True,  # generates a claim; response_verifier checks groundedness
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        question = input_data.get("question", "")
        top_k = input_data.get("top_k", 3)
        file_id = input_data.get("file_id")

        agent_result = knowledge_agent.run(
            AgentContext(owner_id=context.owner_id, db=db, execution_mode=context.execution_mode,
                         timeout=context.timeout, request_id=context.request_id, metadata=context.metadata),
            KnowledgeAnswerInput(question=question, top_k=top_k, file_id=file_id),
        )
        res = agent_result.output

        # Real values from the generation call, not hardcoded placeholders
        # (Phase 10 token audit, 2026-09-20 -- this previously claimed
        # "openai/openrouter"/"gpt-4o-mini" regardless of what actually ran,
        # including when it was Ollama local). None when the answer came
        # from the canned fallback rather than a real completion.
        handler_result: dict[str, Any] = {
            "result": res.model_dump(),
            "provider": res.provider,
            "model": res.model,
        }
        if res.runtime:
            handler_result["runtime"] = res.runtime
        if res.input_tokens is not None and res.output_tokens is not None:
            handler_result["tokens"] = {
                "input": res.input_tokens,
                "output": res.output_tokens,
                "total": res.total_tokens,
            }
        return handler_result


class DatabaseQueryHandler(ExecutionHandler):
    metadata = CapabilityMetadata(
        description="Natural-language to SQL over the sample enterprise DB. "
                     "SQLValidator enforces a read-only AST allowlist before execution.",
        risk_level="medium",  # generated SQL, even if read-only-enforced
        side_effect="read_only",
        requires_verification=True,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        question = input_data.get("question", "")
        limit = input_data.get("limit", 20)

        agent_result = data_agent.run(
            AgentContext(owner_id=context.owner_id, db=db, execution_mode=context.execution_mode,
                         timeout=context.timeout, request_id=context.request_id, metadata=context.metadata),
            DataAgentInput(question=question, limit=limit, enforce_owner_scope=False),
        )
        res = agent_result.output

        # Real values from whichever LLM call produced them, not hardcoded
        # placeholders (Phase 10 token audit, 2026-09-20 -- "nl-to-sql-v1" was
        # never a real model name). "postgresql" is kept as the fallback
        # provider label when both the SQL-generation and explanation calls
        # failed: the database read itself still genuinely ran, unlike the
        # discarded rag_answer placeholders which were never true.
        handler_result: dict[str, Any] = {
            "result": res.model_dump(),
            "provider": res.provider or "postgresql",
            "model": res.model or "nl-to-sql-v1",
        }
        if res.runtime:
            handler_result["runtime"] = res.runtime
        if res.input_tokens is not None and res.output_tokens is not None:
            handler_result["tokens"] = {
                "input": res.input_tokens,
                "output": res.output_tokens,
                "total": res.total_tokens,
            }
        return handler_result


class DatabaseReportHandler(ExecutionHandler):
    """
    Phase 18: the unattended-scheduled-execution counterpart to
    DatabaseQueryHandler. Same pipeline, but with
    enforce_owner_scope=True -- the generated SQL is AST-rejected outright
    if it lacks the owner-scoping predicate, since no human reviews it
    before it runs on a schedule (see SQLValidator.validate_sql and
    DatabaseAgent.process_query's enforce_owner_scope parameter).
    """
    metadata = CapabilityMetadata(
        description="Scheduled natural-language-to-SQL report. Unlike database_query, the "
                     "generated SQL is rejected outright if it lacks an AST-verified owner-scoping "
                     "predicate, since no human reviews it before each scheduled run.",
        risk_level="medium",
        side_effect="read_only",
        requires_verification=True,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        question = input_data.get("question", "")
        limit = input_data.get("limit", 20)

        agent_result = data_agent.run(
            AgentContext(owner_id=context.owner_id, db=db, execution_mode=context.execution_mode,
                         timeout=context.timeout, request_id=context.request_id, metadata=context.metadata),
            DataAgentInput(question=question, limit=limit, enforce_owner_scope=True),
        )
        res = agent_result.output

        handler_result: dict[str, Any] = {
            "result": res.model_dump(),
            "provider": res.provider or "postgresql",
            "model": res.model or "nl-to-sql-v1",
        }
        if res.runtime:
            handler_result["runtime"] = res.runtime
        if res.input_tokens is not None and res.output_tokens is not None:
            handler_result["tokens"] = {
                "input": res.input_tokens,
                "output": res.output_tokens,
                "total": res.total_tokens,
            }
        return handler_result


from app.schemas.runtime import RuntimeGenerateRequest
from app.services.runtime_service import runtime_service


class TextGenerationHandler(ExecutionHandler):
    metadata = CapabilityMetadata(
        description="Freeform local/cloud text generation, routed by the privacy classifier.",
        risk_level="medium",
        side_effect="read_only",  # generates text only; nothing external is sent/written here
        requires_verification=True,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        prompt = input_data.get("prompt", "")
        system_prompt = input_data.get("system_prompt")
        model = input_data.get("model")

        runtime_req = RuntimeGenerateRequest(
            prompt=prompt,
            system_prompt=system_prompt,
            execution_mode=context.execution_mode,
            model=model,
            timeout=context.timeout,
            request_id=context.request_id,
            execution_id=context.execution_id,
            metadata=context.metadata,
        )

        res = runtime_service.generate(runtime_req)

        return {
            "result": {"generated_text": res.completion},
            "provider": res.provider,
            "model": res.model,
            "runtime": res.runtime,
            "latency_ms": res.latency_ms,
            "tokens": {
                "input": res.input_tokens,
                "output": res.output_tokens,
                "total": res.total_tokens,
            },
            # AMOF-X Phase 3: the structured routing decision (placement,
            # predicted_quality/cost/latency, risk, routing_confidence) was
            # being computed by runtime_service.generate() and then silently
            # dropped here -- nothing downstream of the handler boundary ever
            # read res.routing, so the "checkable audit trail" the router's
            # own docstring claims did not actually reach persistence or the
            # API response. Surfacing it here is what makes it real.
            "routing": res.routing,
        }


class DocumentSummaryHandler(ExecutionHandler):
    metadata = CapabilityMetadata(
        description="Summarizes a document (by file_id or raw text) via local/cloud generation.",
        risk_level="low",
        side_effect="read_only",
        requires_verification=True,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        file_id = input_data.get("file_id")
        text_content = input_data.get("text")

        agent_result = document_ops_agent.run(
            AgentContext(owner_id=context.owner_id, db=db, execution_mode=context.execution_mode,
                         timeout=context.timeout, request_id=context.request_id,
                         execution_id=context.execution_id, metadata=context.metadata),
            DocumentSummaryHandlerInput(file_id=file_id, text=text_content),
        )
        res = agent_result.output

        return {
            "result": {"summary": res.completion},
            "provider": res.provider,
            "model": res.model,
            "runtime": res.runtime,
            "latency_ms": res.latency_ms,
            "tokens": {
                "input": res.input_tokens,
                "output": res.output_tokens,
                "total": res.total_tokens,
            },
            "routing": res.routing,
        }


from app.services.google_connector_service import GoogleConnectorService


class GmailSendHandler(ExecutionHandler):
    """
    AMOF-X Phase 2 dependency, pulled forward from Phase 5's planned scope:
    the existing planner (app/supervisor/planner.py) has always produced a
    "gmail.send" PlanStep for send-email intents, but that capability was
    never actually registered here -- TaskRegistry simply didn't know about
    it, and validate_dag_plan didn't check capability existence, so the gap
    was silent. Adding capability-existence validation (Phase 2) surfaced it
    immediately: existing approval-flow tests broke because they legitimately
    need this step to resolve. This wraps the real, already-working
    GoogleConnectorService.send_email -- no new Gmail integration, no fake
    send, just registering the real one so the registry stops lying about
    what capabilities exist.
    """
    metadata = CapabilityMetadata(
        description="Sends an email via the authenticated user's Gmail account.",
        risk_level="high",
        side_effect="external_communication",
        requires_verification=True,
        requires_human_approval=True,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        try:
            user_id = int(context.owner_id)
        except (TypeError, ValueError):
            raise ValueError(
                f"owner_id {context.owner_id!r} is not a users.id, so this send "
                "cannot be attributed to a real Gmail account."
            ) from None

        to = input_data.get("to", "")
        subject = input_data.get("subject", "")
        body = input_data.get("body", "")

        result = GoogleConnectorService.send_email(
            db=db, user_id=user_id, to=to, subject=subject, body=body,
        )
        return {
            "result": {"sent": True, "to": to, "subject": subject, "gmail_response": result},
            "provider": "gmail",
            "model": None,
        }


from app.services.workgraph_service import workgraph_service


class CreateTaskHandler(ExecutionHandler):
    """
    AMOF-X Phase 6: creates a real WorkGraph task from a workflow node (a
    CDRP escalation, a Meeting action item, or a direct request) -- the same
    table and constraints a human-created task uses, distinguished only by
    created_by/source_type (per target spec §39's own worked example: a
    LOW_SIDE_EFFECT capability, reversible, no approval required, but still
    audited through the normal execution-record path).
    """
    metadata = CapabilityMetadata(
        description="Creates a tracked WorkGraph task, optionally inside a project and depending on other tasks.",
        risk_level="low",
        side_effect="reversible_write",
        requires_verification=False,
        requires_human_approval=False,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        title = input_data.get("title", "")
        if not title.strip():
            raise ValueError("CreateTaskHandler requires a non-empty 'title'.")

        task = workgraph_service.create_task(
            db=db,
            owner_id=context.owner_id,
            title=title,
            description=input_data.get("description"),
            project_id=input_data.get("project_id"),
            assignee=input_data.get("assignee"),
            priority=input_data.get("priority", "medium"),
            due_date=input_data.get("due_date"),
            # The caller declares provenance explicitly -- this handler does
            # not guess "ai" vs a specific source_type from context, since
            # different callers (CDRP's critical-escalation path, Meeting's
            # opt-in action-item conversion) mean different things by it.
            created_by=input_data.get("created_by", "ai"),
            source_type=input_data.get("source_type", "manual"),
            source_ref=input_data.get("source_ref"),
            depends_on=input_data.get("depends_on"),
        )
        return {
            "result": workgraph_service.to_response_dto(db, task).model_dump(mode="json"),
            "provider": "workgraph",
            "model": None,
        }


from app.agents.meeting_agent import meeting_extraction_agent, MeetingExtractionInput
from app.services.meeting_service import meeting_service


class MeetingTranscriptHandler(ExecutionHandler):
    """
    AMOF-X Phase 7: extracts summary/decisions/action_items/risks from a
    meeting transcript and persists a Meeting + MeetingActionItem rows.
    Extraction alone is read-only -- converting an action item into a
    WorkGraph task is a separate, already-audited capability
    # (create task capability) the caller invokes explicitly, never automatic here
    # (avoids task-spam from noisy transcripts, per PHASE_07.md).
    """
    metadata = CapabilityMetadata(
        description="Extracts summary/decisions/action items/risks from a meeting transcript (upload/export/paste, not a live Meet API pull).",
        risk_level="low",
        side_effect="read_only",
        # Returns a structured extraction, not a claim to ground-check against
        # retrieved context -- same reasoning as search / task creation handlers.
        requires_verification=False,
        requires_human_approval=False,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        transcript_text = input_data.get("transcript_text", "")
        if not transcript_text.strip():
            raise ValueError("MeetingTranscriptHandler requires non-empty 'transcript_text'.")

        transcript_source = input_data.get("transcript_source", "manual_paste")

        meeting = meeting_service.create_meeting(
            db=db,
            owner_id=context.owner_id,
            transcript_text=transcript_text,
            transcript_source=transcript_source,
        )

        agent_result = meeting_extraction_agent.run(
            AgentContext(owner_id=context.owner_id, db=db, execution_mode=context.execution_mode,
                         timeout=context.timeout, request_id=context.request_id, metadata=context.metadata),
            MeetingExtractionInput(transcript_text=transcript_text),
        )
        extraction = agent_result.output.model_dump()

        meeting = meeting_service.store_extraction(db, meeting, extraction)

        return {
            "result": {"meeting_id": meeting.id, **extraction},
            "provider": "meeting_agent",
            "model": None,
        }


from datetime import datetime, timedelta, timezone

from app.agents.calendar_agent import calendar_agent, CalendarViewInput
from app.agents.task_agent import task_agent, TaskViewInput
from app.agents.inbox_agent import inbox_triage_agent, InboxListInput, InboxClassifyInput, InboxDraftInput
# CalendarService is not called directly in this module anymore (DigestHandler
# delegates to CalendarAgent) -- kept imported so
# tests/test_digest.py's `patch("app.execution.contracts.CalendarService.list_events")`
# still resolves. Patching a staticmethod on the class object affects every
# caller regardless of which module's name binding reaches it, so this stays
# behaviourally identical to before the refactor.
from app.services.calendar_service import CalendarService


def _render_digest_text(sections: dict[str, Any]) -> str:
    """
    Plain-text v1 per PHASE_16.md's risk note (keep formatting simple).
    An unavailable section is named as unavailable rather than dropped, so
    the text can never imply "nothing to report" when it actually means
    "could not check".
    """
    lines = []
    for key, label in (
        ("unread_email", "Unread email"),
        ("today_events", "Today's events"),
        ("overdue_tasks", "Overdue tasks"),
    ):
        section = sections.get(key, {})
        if not section.get("available"):
            lines.append(f"{label}: unavailable ({section.get('reason', 'unknown error')})")
            continue
        lines.append(f"{label}: {section['count']}")
        if key == "today_events" and section.get("conflicts"):
            for conflict in section["conflicts"]:
                lines.append(f"  conflict: {conflict['event_a']} overlaps {conflict['event_b']}")
    return "\n".join(lines)


def _suggested_actions(sections: dict[str, Any]) -> list[str]:
    """
    Heuristic, not generated -- each suggestion is a direct readout of a
    count already computed above, so there is nothing here for a model to
    fabricate or get wrong.
    """
    actions: list[str] = []
    overdue = sections.get("overdue_tasks", {})
    if overdue.get("available") and overdue.get("count"):
        actions.append(f"Follow up on {overdue['count']} overdue task(s).")
    upcoming = sections.get("upcoming_deadlines", {})
    if upcoming.get("available") and upcoming.get("count"):
        actions.append(f"Plan for {upcoming['count']} task(s) due in the next 3 days.")
    at_risk = sections.get("at_risk_commitments", {})
    if at_risk.get("available") and at_risk.get("count"):
        actions.append(f"Check in on {at_risk['count']} at-risk commitment(s).")
    conflicts = (sections.get("today_events", {}) or {}).get("conflicts") or []
    if conflicts:
        actions.append(f"Resolve {len(conflicts)} calendar conflict(s) today.")
    unread = sections.get("unread_email", {})
    if unread.get("available") and unread.get("count"):
        actions.append(f"Review {unread['count']} unread email(s).")
    return actions


class DigestHandler(ExecutionHandler):
    """
    Phase 16: read-only composition of what the user would otherwise open
    three apps to check -- unread Gmail, today's calendar (with conflicts),
    and overdue WorkGraph tasks.

    Every read is keyed to context.owner_id. There is deliberately no
    "all users" path here at all: a digest is assembled for one owner or not
    at all, so a cross-user leak would require adding a parameter that
    doesn't exist rather than merely getting a filter wrong.

    Each section degrades independently and *says so*. A user whose Gmail
    token has expired gets "unavailable (<reason>)", never an empty list --
    silently reporting zero unread mail when the connector failed would be a
    wrong answer presented as a real one.
    """

    metadata = CapabilityMetadata(
        description="Read-only daily digest: unread email, today's calendar events and conflicts, and overdue tasks.",
        risk_level="low",
        side_effect="read_only",
        # Composes already-fetched connector data; there is no generated
        # claim to ground-check, same as the other read-only handlers.
        requires_verification=False,
        requires_human_approval=False,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        owner_id = context.owner_id
        try:
            user_id = int(owner_id)
        except (TypeError, ValueError):
            raise ValueError(
                f"owner_id {owner_id!r} is not a users.id, so this digest cannot "
                "be scoped to a real account's connectors."
            ) from None

        max_emails = int(input_data.get("max_emails", 10))
        now = datetime.now(timezone.utc)
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = day_start + timedelta(days=1)

        sections: dict[str, Any] = {}

        agent_ctx = AgentContext(owner_id=owner_id, db=db, execution_mode=context.execution_mode,
                                  timeout=context.timeout, request_id=context.request_id,
                                  metadata=context.metadata)

        # --- Unread email -------------------------------------------------
        # Reads via InboxAgent's list mode (InboxListInput) -- a raw fetch,
        # not the classify path -- so digest generation does not add an LLM
        # classification call (and its cost/latency) that was never part of
        # this capability's behaviour before Phase 23.
        try:
            findings = inbox_triage_agent.run(agent_ctx, InboxListInput(max_emails=max_emails)).output
            messages = findings.messages
            sections["unread_email"] = {
                "available": True,
                "count": len(messages),
                "items": [
                    {"subject": m.get("subject"), "from": m.get("from"), "snippet": m.get("snippet")}
                    for m in messages
                ],
            }
        except Exception as exc:
            sections["unread_email"] = {"available": False, "reason": str(exc)}

        # --- Today's calendar ---------------------------------------------
        try:
            schedule = calendar_agent.run(
                agent_ctx,
                CalendarViewInput(time_min=day_start.isoformat(), time_max=day_end.isoformat()),
            ).output
            events = schedule.events
            sections["today_events"] = {
                "available": True,
                "count": len(events),
                "items": [
                    {
                        "summary": e.get("summary", "(no title)"),
                        "start": (e.get("start") or {}).get("dateTime") or (e.get("start") or {}).get("date"),
                    }
                    for e in events
                ],
                "conflicts": schedule.conflicts,
            }
        except Exception as exc:
            sections["today_events"] = {"available": False, "reason": str(exc)}

        # --- Overdue tasks --------------------------------------------------
        # Queried via TaskAgent, which filters on owner_id -- the same
        # scoping every interactive task read goes through.
        try:
            task_view = task_agent.run(agent_ctx, TaskViewInput()).output
            overdue = task_view.overdue
            sections["overdue_tasks"] = {
                "available": True,
                "count": len(overdue),
                "items": [
                    {"id": t["id"], "title": t["title"], "due_date": t["due_date"], "priority": t["priority"]}
                    for t in overdue
                ],
            }
        except Exception as exc:
            sections["overdue_tasks"] = {"available": False, "reason": str(exc)}

        # --- Upcoming deadlines (not yet overdue, due within 3 days) -------
        try:
            task_view = task_agent.run(agent_ctx, TaskViewInput()).output
            soon = day_end + timedelta(days=3)
            upcoming = [
                t for t in task_view.tasks
                if t.get("due_date") and t.get("status") != "done"
                and day_end.isoformat() <= t["due_date"] < soon.isoformat()
            ]
            sections["upcoming_deadlines"] = {"available": True, "count": len(upcoming), "items": upcoming}
        except Exception as exc:
            sections["upcoming_deadlines"] = {"available": False, "reason": str(exc)}

        # --- At-risk commitments (Commitment Tracker) ----------------------
        try:
            at_risk = commitment_service.list_commitments(db, owner_id, status="at_risk")
            sections["at_risk_commitments"] = {
                "available": True,
                "count": len(at_risk),
                "items": [
                    {"id": c.id, "description": c.description, "due_date": c.due_date, "responsible_party": c.responsible_party}
                    for c in at_risk
                ],
            }
        except Exception as exc:
            sections["at_risk_commitments"] = {"available": False, "reason": str(exc)}

        sections["suggested_actions"] = _suggested_actions(sections)

        return {
            "result": {
                "generated_at": now.isoformat(),
                "owner_id": owner_id,
                "summary": _render_digest_text(sections),
                **sections,
            },
            "provider": "digest",
            "model": None,
        }


class InboxClassifyHandler(ExecutionHandler):
    """
    Phase 19: reads the owner's unread Gmail (or an explicitly supplied
    message list) and labels each message urgent/needs_reply/fyi/spam.

    Read-only by construction: it fetches and classifies, and returns
    suggestions. It does not label, archive, delete or reply in Gmail --
    v1 ships as assistive triage, so a misclassification costs the user a
    glance, not a lost email (PHASE_19.md risk note).
    """
    metadata = CapabilityMetadata(
        description="Classifies the owner's unread email as urgent / needs_reply / fyi / spam (suggestion only; nothing is changed in Gmail).",
        risk_level="low",
        side_effect="read_only",
        # Returns a structured labelling of retrieved data, not a claim to
        # ground-check -- same as the other extraction/triage handlers.
        requires_verification=False,
        requires_human_approval=False,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        messages = input_data.get("messages")
        max_emails = int(input_data.get("max_emails", 10))

        agent_result = inbox_triage_agent.run(
            AgentContext(owner_id=context.owner_id, db=db, execution_mode=context.execution_mode,
                         timeout=context.timeout, request_id=context.request_id, metadata=context.metadata),
            InboxClassifyInput(messages=messages, max_emails=max_emails),
        )
        classifications = agent_result.output.messages
        counts: dict[str, int] = {}
        for item in classifications:
            counts[item["label"]] = counts.get(item["label"], 0) + 1

        return {
            "result": {"classifications": classifications, "counts": counts},
            "provider": "inbox_agent",
            "model": None,
        }


class InboxDraftReplyHandler(ExecutionHandler):
    """
    Phase 19: generates reply *text* for a needs_reply message.

    Nothing leaves the system here. The returned draft carries
    send_capability="gmail.send" to say explicitly how it is sent: through
    the one registered, approval-gated send capability, whose approval claim
    the executor enforces (see ExecutionExecutor's approval gate). This
    handler creates no Gmail draft and performs no send, so it adds no
    second path that would need its own gate.
    """
    metadata = CapabilityMetadata(
        description="Drafts a reply to a single email. Produces text only -- sending requires the separate, approval-gated gmail.send capability.",
        risk_level="low",
        side_effect="read_only",
        requires_verification=False,
        requires_human_approval=False,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        message = input_data.get("message")
        message_id = input_data.get("message_id")
        if not message and not message_id:
            raise ValueError(
                "InboxDraftReplyHandler requires either 'message' (a Gmail message dict) "
                "or 'message_id'."
            )

        agent_result = inbox_triage_agent.run(
            AgentContext(owner_id=context.owner_id, db=db, execution_mode=context.execution_mode,
                         timeout=context.timeout, request_id=context.request_id, metadata=context.metadata),
            InboxDraftInput(
                message=dict(message) if message else None,
                message_id=str(message_id) if message_id else None,
                instructions=input_data.get("instructions"),
            ),
        )
        draft = agent_result.output

        return {
            "result": {**draft, "sent": False, "send_capability": "gmail.send"},
            "provider": "inbox_agent",
            "model": None,
        }


from app.agents.inbox_agent import inbox_agent
from app.services.commitment_service import commitment_service
from app.services.meeting_service import meeting_service as _meeting_service_for_commitments


class CommitmentScanHandler(ExecutionHandler):
    """
    Commitment Tracker: scans the owner's unread Gmail (via InboxAgent's
    commitment extraction) and every meeting action item they have, and
    upserts each as a tracked Commitment row.

    Read + upsert only -- this handler never calls workgraph_service.create_task,
    so it structurally cannot duplicate a task. A meeting action item that was
    already converted to a task (item.workgraph_task_id set) is linked, not
    recreated; commitment_service's (owner_id, source_type, source_ref) unique
    key makes a rescan update the same row rather than insert a new one.
    """
    metadata = CapabilityMetadata(
        description="Scans Gmail and meeting action items for commitments/promises and tracks them (pending/completed/at_risk).",
        risk_level="low",
        side_effect="reversible_write",
        requires_verification=False,
        requires_human_approval=False,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        owner_id = context.owner_id
        max_emails = int(input_data.get("max_emails", 10))
        agent_ctx = AgentContext(owner_id=owner_id, db=db, execution_mode=context.execution_mode,
                                  timeout=context.timeout, request_id=context.request_id,
                                  metadata=context.metadata)

        messages = inbox_triage_agent.run(agent_ctx, InboxListInput(max_emails=max_emails)).output.messages
        gmail_commitments = inbox_agent.extract_commitments(
            list(messages), execution_mode=context.execution_mode,
            timeout=context.timeout, request_id=context.request_id,
        )

        created = 0
        updated = 0

        for item in gmail_commitments:
            _, was_created = commitment_service.upsert_commitment(
                db=db, owner_id=owner_id,
                description=item["description"],
                source_type="gmail",
                source_ref=item["id"],
                responsible_party=item.get("owner"),
                due_date=item.get("due_date"),
            )
            created += int(was_created)
            updated += int(not was_created)

        action_items = _meeting_service_for_commitments.list_action_items_for_owner(db, owner_id)
        for action_item in action_items:
            _, was_created = commitment_service.upsert_commitment(
                db=db, owner_id=owner_id,
                description=action_item.description,
                source_type="meeting",
                source_ref=action_item.id,
                responsible_party=action_item.owner,
                due_date=action_item.due_date,
                linked_task_id=action_item.workgraph_task_id,
            )
            created += int(was_created)
            updated += int(not was_created)

        return {
            "result": {
                "scanned_gmail": len(messages),
                "scanned_meeting_items": len(action_items),
                "created": created,
                "updated": updated,
            },
            "provider": "commitment_service",
            "model": None,
        }
