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
from typing import Any, Optional

from app.agents.calendar_agent import calendar_agent, CalendarViewInput
from app.agents.task_agent import task_agent, TaskViewInput
from app.agents.inbox_agent import inbox_triage_agent, InboxListInput, InboxClassifyInput, InboxDraftInput, inbox_agent
from app.services.calendar_service import CalendarService
from app.services.google_connector_service import GoogleConnectorService
from app.services.commitment_service import commitment_service
from app.utils.timezone import local_now, local_day_start, local_day_end, resolve_timezone, DEFAULT_TZ
from app.services.digest_email_service import categorize_email_by_date, normalize_email_meta, parse_email_datetime
from app.connectors.google.exceptions import GoogleReauthRequiredError, GoogleServiceDisabledError, GoogleNotConnectedError
from app.models.user import User


class ActionDict(dict):
    """
    Dict that returns True for `sub in action` if `sub` is contained in any string value,
    preserving backward compatibility with legacy tests while supplying rich structured data.
    """
    def __contains__(self, item: Any) -> bool:
        if super().__contains__(item):
            return True
        if isinstance(item, str):
            item_lower = item.lower()
            return any(isinstance(v, str) and item_lower in v.lower() for v in self.values())
        return False


def _render_digest_text(sections: dict[str, Any]) -> str:
    """
    Plain-text representation. An unavailable section is named as unavailable
    rather than dropped so the text never implies 'nothing to report' when it
    means 'could not check'.
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
        lines.append(f"{label}: {section.get('count', 0)}")
        if key == "today_events" and section.get("conflicts"):
            for conflict in section["conflicts"]:
                lines.append(f"  conflict: {conflict['event_a']} overlaps {conflict['event_b']}")
    return "\n".join(lines)


def _generate_ai_summary(sections: dict[str, Any], user_tz: str) -> dict[str, Any]:
    """
    Deterministic AI-ready daily summary synthesizing real retrieved data.
    """
    emails = sections.get("unread_email", {})
    events = sections.get("today_events", {})
    overdue = sections.get("overdue_tasks", {})
    upcoming = sections.get("upcoming_deadlines", {})
    commitments = sections.get("at_risk_commitments", {})

    priorities: list[str] = []
    warnings: list[str] = []
    summary_parts: list[str] = []

    events_count = events.get("count", 0) if events.get("available") else 0
    overdue_count = overdue.get("count", 0) if overdue.get("available") else 0
    unread_count = emails.get("total_unread", emails.get("count", 0)) if emails.get("available") else 0
    urgent_count = emails.get("urgent", 0) if emails.get("available") else 0
    needs_reply_count = emails.get("needs_reply", 0) if emails.get("available") else 0

    summary_parts.append(
        f"Good morning! You have {events_count} event{'s' if events_count != 1 else ''} scheduled today, "
        f"{overdue_count} overdue task{'s' if overdue_count != 1 else ''}, and "
        f"{unread_count} unread email{'s' if unread_count != 1 else ''}."
    )

    if urgent_count > 0 or needs_reply_count > 0:
        items = emails.get("items", [])
        top_urgent = next((m for m in items if m.get("classification") in ("urgent", "needs_reply")), None)
        if top_urgent:
            priorities.append(f"Respond to '{top_urgent.get('subject')}' from {top_urgent.get('sender')}")
            summary_parts.append(f"Your top email priority is '{top_urgent.get('subject')}'.")

    if overdue_count > 0:
        items = overdue.get("items", [])
        top_task = items[0] if items else None
        if top_task:
            priorities.append(f"Complete overdue task: {top_task.get('title')}")
            summary_parts.append(f"Task '{top_task.get('title')}' is overdue and needs immediate resolution.")

    conflicts = events.get("conflicts", [])
    if conflicts:
        for c in conflicts:
            warnings.append(f"Schedule conflict: '{c.get('event_a')}' overlaps with '{c.get('event_b')}'.")
        summary_parts.append(f"Notice: You have {len(conflicts)} scheduling conflict{'s' if len(conflicts) > 1 else ''} today.")

    next_event = events.get("next_event")
    if next_event:
        priorities.append(f"Upcoming meeting: {next_event.get('title') or next_event.get('summary')} at {next_event.get('start')}")

    at_risk_count = commitments.get("count", 0) if commitments.get("available") else 0
    if at_risk_count > 0:
        c_items = commitments.get("items", [])
        top_c = c_items[0] if c_items else None
        if top_c:
            warnings.append(f"At-risk commitment: '{top_c.get('description')}' ({top_c.get('risk_reason', 'Pending')})")
            summary_parts.append(f"You have {at_risk_count} commitment{'s' if at_risk_count != 1 else ''} marked at risk.")

    focus_text = priorities[0] if priorities else "Clear outstanding emails and review your agenda."

    return {
        "text": " ".join(summary_parts),
        "priorities": priorities[:4],
        "warnings": warnings,
        "focus": focus_text,
        "is_ai_generated": False,
    }


def _suggested_actions(sections: dict[str, Any]) -> list[Any]:
    """
    Generate ranked, structured, evidence-grounded action items.
    """
    actions: list[ActionDict] = []
    act_idx = 1

    # 1. Overdue tasks (highest urgency)
    overdue = sections.get("overdue_tasks", {})
    if overdue.get("available") and overdue.get("count", 0) > 0:
        overdue_items = overdue.get("items", [])
        top_task = overdue_items[0] if overdue_items else None
        desc = f"Complete overdue task '{top_task['title']}'." if top_task else f"Follow up on {overdue['count']} overdue task(s)."
        task_id = top_task.get("id") if top_task else None
        actions.append(ActionDict({
            "id": f"act_{act_idx}",
            "title": f"Follow up on {overdue['count']} overdue task(s)",
            "description": desc,
            "priority": "urgent",
            "reason": "Overdue deadline requires immediate attention",
            "action_type": "complete_task",
            "related_entity": {"type": "task", "id": str(task_id)} if task_id else {"type": "task"},
            "source_reference": top_task.get("title", "") if top_task else "",
        }))
        act_idx += 1

    # 2. Calendar conflicts
    conflicts = (sections.get("today_events", {}) or {}).get("conflicts") or []
    if conflicts:
        conflict = conflicts[0]
        actions.append(ActionDict({
            "id": f"act_{act_idx}",
            "title": f"Resolve {len(conflicts)} calendar conflict(s) today",
            "description": f"Conflict detected: '{conflict.get('event_a')}' overlaps '{conflict.get('event_b')}'.",
            "priority": "urgent",
            "reason": "Overlapping schedule requires rescheduling",
            "action_type": "resolve_conflict",
            "related_entity": {"type": "calendar"},
            "source_reference": f"{conflict.get('event_a')} / {conflict.get('event_b')}",
        }))
        act_idx += 1

    # 3. Urgent or Needs Reply emails
    unread = sections.get("unread_email", {})
    if unread.get("available") and unread.get("count", 0) > 0:
        items = unread.get("items", [])
        urgent_emails = [m for m in items if m.get("classification") in ("urgent", "needs_reply") or m.get("is_important")]
        if urgent_emails:
            top_email = urgent_emails[0]
            actions.append(ActionDict({
                "id": f"act_{act_idx}",
                "title": f"Reply to '{top_email.get('subject', 'email')}'",
                "description": f"From {top_email.get('sender', 'Sender')}: {top_email.get('snippet', '')[:100]}",
                "priority": "urgent" if top_email.get("classification") == "urgent" else "high",
                "reason": top_email.get("classification_reason") or "Requires reply or review",
                "action_type": "reply_email",
                "related_entity": {"type": "email", "id": str(top_email.get("id"))},
                "source_reference": top_email.get("subject", ""),
            }))
            act_idx += 1
        else:
            actions.append(ActionDict({
                "id": f"act_{act_idx}",
                "title": f"Review {unread['count']} unread email(s)",
                "description": "Catch up on new unread messages in your inbox.",
                "priority": "medium",
                "reason": "Keep inbox up to date",
                "action_type": "open_email",
                "related_entity": {"type": "email"},
                "source_reference": "inbox",
            }))
            act_idx += 1

    # 4. At-risk commitments
    at_risk = sections.get("at_risk_commitments", {})
    if at_risk.get("available") and at_risk.get("count", 0) > 0:
        at_risk_items = at_risk.get("items", [])
        top_commit = at_risk_items[0] if at_risk_items else None
        desc = f"At-risk commitment: {top_commit.get('description', '')}" if top_commit else f"Check in on {at_risk['count']} at-risk commitment(s)."
        actions.append(ActionDict({
            "id": f"act_{act_idx}",
            "title": f"Check in on {at_risk['count']} at-risk commitment(s)",
            "description": desc,
            "priority": "high",
            "reason": top_commit.get("risk_reason") or "Approaching deadline with pending status",
            "action_type": "review_commitment",
            "related_entity": {"type": "commitment", "id": str(top_commit.get("id"))} if top_commit else {"type": "commitment"},
            "source_reference": top_commit.get("description", "") if top_commit else "",
        }))
        act_idx += 1

    # 5. Upcoming deadlines
    upcoming = sections.get("upcoming_deadlines", {})
    if upcoming.get("available") and upcoming.get("count", 0) > 0:
        upcoming_items = upcoming.get("items", [])
        top_upcoming = upcoming_items[0] if upcoming_items else None
        actions.append(ActionDict({
            "id": f"act_{act_idx}",
            "title": f"Plan for {upcoming['count']} task(s) due in the next 3 days",
            "description": f"Prepare to complete '{top_upcoming.get('title')}'." if top_upcoming else "Review upcoming deadlines.",
            "priority": "medium",
            "reason": "Upcoming deadline proximity",
            "action_type": "open_task",
            "related_entity": {"type": "task", "id": str(top_upcoming.get("id"))} if top_upcoming else {"type": "task"},
            "source_reference": top_upcoming.get("title", "") if top_upcoming else "",
        }))
        act_idx += 1

    # 6. Today's next event
    events_section = sections.get("today_events", {})
    next_event = events_section.get("next_event")
    if next_event:
        actions.append(ActionDict({
            "id": f"act_{act_idx}",
            "title": f"Prepare for upcoming meeting: {next_event.get('title') or next_event.get('summary')}",
            "description": f"Scheduled at {next_event.get('start')}. {next_event.get('prep_notes', '')}".strip(),
            "priority": "medium",
            "reason": "Next upcoming event today",
            "action_type": "prepare_meeting",
            "related_entity": {"type": "calendar", "id": str(next_event.get("id"))},
            "source_reference": next_event.get("title") or next_event.get("summary") or "",
        }))
        act_idx += 1

    return actions


class DigestHandler(ExecutionHandler):
    """
    Phase 16: read-only composition of what the user would otherwise open
    three apps to check -- unread Gmail, today's calendar (with conflicts),
    and overdue WorkGraph tasks.

    Every read is keyed to context.owner_id. There is deliberately no
    'all users' path here at all: a digest is assembled for one owner or not
    at all, so a cross-user leak would require adding a parameter that
    doesn't exist rather than merely getting a filter wrong.

    Each section degrades independently and says so. A user whose Gmail
    token has expired gets 'unavailable (<reason>)', never an empty list --
    silently reporting zero unread mail when the connector failed would be a
    wrong answer presented as a real one.
    """

    metadata = CapabilityMetadata(
        description="Read-only daily digest: unread email, today's calendar events and conflicts, and overdue tasks.",
        risk_level="low",
        side_effect="read_only",
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

        max_emails = min(int(input_data.get("max_emails", 50)), 100)

        # Resolve user's timezone; fallback to UTC safely
        user_tz = DEFAULT_TZ
        try:
            user_row = db.query(User).filter(User.id == user_id).first()
            if user_row and getattr(user_row, "timezone", None):
                user_tz = user_row.timezone
        except Exception:
            user_tz = DEFAULT_TZ

        now_local = local_now(user_tz)
        day_start = local_day_start(user_tz)
        day_end = local_day_end(user_tz)

        sections: dict[str, Any] = {}

        agent_ctx = AgentContext(
            owner_id=owner_id,
            db=db,
            execution_mode=context.execution_mode,
            timeout=context.timeout,
            request_id=context.request_id,
            metadata=context.metadata,
        )

        # --- Unread email -------------------------------------------------
        try:
            findings = inbox_triage_agent.run(agent_ctx, InboxListInput(max_emails=max_emails)).output
            messages = findings.messages

            # Attempt accurate total count from connector if supported
            total_unread_est = len(messages)
            has_more = False
            next_page_token = None
            try:
                summary_data = GoogleConnectorService.get_unread_summary(db=db, user_id=user_id, limit=max_emails)
                if isinstance(summary_data, dict):
                    total_unread_est = summary_data.get("total_unread", len(messages))
                    has_more = summary_data.get("has_more", False)
                    next_page_token = summary_data.get("next_page_token")
            except Exception:
                pass

            categories = {
                "today": 0, "yesterday": 0, "older": 0,
                "important": 0, "urgent": 0, "needs_reply": 0, "fyi": 0, "spam": 0,
            }
            emails_today = []
            emails_yesterday = []
            emails_older = []
            emails_important = []
            classified_items = []

            for m in messages:
                meta = normalize_email_meta(m, user_tz)
                date_cat = categorize_email_by_date(m, user_tz)
                meta["date_category"] = date_cat

                if date_cat == "today":
                    categories["today"] += 1
                    emails_today.append(meta)
                elif date_cat == "yesterday":
                    categories["yesterday"] += 1
                    emails_yesterday.append(meta)
                else:
                    categories["older"] += 1
                    emails_older.append(meta)

                if meta.get("is_important"):
                    categories["important"] += 1
                    emails_important.append(meta)

                classified_items.append(meta)

            # Deterministic classification using InboxAgent heuristics (fast, offline-safe, explainable)
            for item in classified_items:
                fallback_res = inbox_agent._fallback(item, "")
                item["classification"] = fallback_res.get("label", "fyi")
                item["classification_reason"] = fallback_res.get("reason", "")
                if fallback_res.get("label") == "urgent":
                    item["priority"] = "urgent"
                    item["is_important"] = True
                elif fallback_res.get("label") == "needs_reply":
                    item["priority"] = "high"

            # Optional LLM refinement if explicitly requested and runtime is available
            if input_data.get("use_llm_classification", False) and context.execution_mode != "mock":
                try:
                    classify_result = inbox_triage_agent.run(
                        agent_ctx,
                        InboxClassifyInput(messages=messages, max_emails=min(max_emails, 10)),
                    ).output
                    for item in classified_items:
                        for cls in (getattr(classify_result, "messages", None) or []):
                            if str(cls.get("id")) == str(item.get("id")):
                                item["classification"] = cls.get("label", item.get("classification"))
                                item["classification_reason"] = cls.get("reason", item.get("classification_reason"))
                except Exception:
                    pass

            for item in classified_items:
                lbl = item.get("classification")
                if lbl == "urgent":
                    categories["urgent"] += 1
                elif lbl == "needs_reply":
                    categories["needs_reply"] += 1
                elif lbl == "fyi":
                    categories["fyi"] += 1
                elif lbl == "spam":
                    categories["spam"] += 1

            sections["unread_email"] = {
                "available": True,
                "count": len(messages),
                "total_unread": total_unread_est,
                "fetched_count": len(messages),
                "classified_count": len(classified_items),
                "displayed_count": min(len(classified_items), 15),
                "today": categories["today"],
                "yesterday": categories["yesterday"],
                "older": categories["older"],
                "important": categories["important"],
                "urgent": categories["urgent"],
                "needs_reply": categories["needs_reply"],
                "fyi": categories["fyi"],
                "spam": categories["spam"],
                "has_more": has_more,
                "next_page_token": next_page_token,
                "items": classified_items[:50],
            }
        except GoogleNotConnectedError:
            sections["unread_email"] = {
                "available": False,
                "reason": "Google account not connected",
                "status": "not_connected",
            }
        except GoogleReauthRequiredError:
            sections["unread_email"] = {
                "available": False,
                "reason": "Gmail access requires reauthorization. Please reconnect your Google account in Settings/Integrations.",
                "status": "reconnect_required",
            }
        except Exception as exc:
            sections["unread_email"] = {"available": False, "reason": str(exc)}

        # --- Today's calendar ---------------------------------------------
        try:
            schedule = calendar_agent.run(
                agent_ctx,
                CalendarViewInput(time_min=day_start.isoformat(), time_max=day_end.isoformat(), limit=50),
            ).output
            raw_events = schedule.events

            parsed_events = []
            for e in raw_events:
                summary = e.get("summary") or "(no title)"
                start_obj = e.get("start") or {}
                end_obj = e.get("end") or {}
                start_str = start_obj.get("dateTime") or start_obj.get("date")
                end_str = end_obj.get("dateTime") or end_obj.get("date")
                is_all_day = bool(start_obj.get("date") and not start_obj.get("dateTime"))

                attendees_raw = e.get("attendees") or []
                participants = [
                    a.get("displayName") or a.get("email") for a in attendees_raw if isinstance(a, dict)
                ]

                # Preparation note heuristic
                prep_notes = ""
                if len(participants) > 1:
                    prep_notes = f"Review agenda and notes for meeting with {', '.join(participants[:2])}."
                elif "review" in summary.lower() or "sync" in summary.lower():
                    prep_notes = "Prepare latest project status and action items."

                meeting_link = (
                    e.get("hangoutLink")
                    or (e.get("conferenceData") or {}).get("entryPoints", [{}])[0].get("uri")
                    or e.get("location") if ("zoom.us" in str(e.get("location")) or "meet.google" in str(e.get("location"))) else None
                )

                parsed_events.append({
                    "id": e.get("id"),
                    "title": summary,
                    "summary": summary,
                    "start": start_str,
                    "end": end_str,
                    "is_all_day": is_all_day,
                    "location": e.get("location"),
                    "meeting_link": meeting_link,
                    "participants": participants,
                    "description": e.get("description", ""),
                    "prep_notes": prep_notes,
                })

            # Find next upcoming event
            next_event = None
            for ev in parsed_events:
                st = ev.get("start")
                if st:
                    ev_dt = parse_email_datetime(st, user_tz)
                    if ev_dt and ev_dt >= now_local:
                        next_event = ev
                        break

            sections["today_events"] = {
                "available": True,
                "count": len(parsed_events),
                "items": parsed_events,
                "conflicts": schedule.conflicts,
                "next_event": next_event,
                "requires_reauth": False,
            }
        except GoogleNotConnectedError:
            sections["today_events"] = {
                "available": False,
                "reason": "Google account not connected",
                "requires_reauth": True,
                "count": 0,
                "items": [],
                "conflicts": [],
            }
        except GoogleReauthRequiredError:
            sections["today_events"] = {
                "available": False,
                "reason": "Google Calendar access requires reauthorization. Please reconnect your Google account in Settings/Integrations.",
                "requires_reauth": True,
                "count": 0,
                "items": [],
                "conflicts": [],
            }
        except GoogleServiceDisabledError:
            sections["today_events"] = {
                "available": False,
                "reason": "Google Calendar API is not enabled in your Google Cloud Project. Please enable it in Google Cloud Console.",
                "requires_reauth": False,
                "count": 0,
                "items": [],
                "conflicts": [],
            }
        except Exception as exc:
            err_str = str(exc)
            if "403" in err_str or "Forbidden" in err_str:
                clean_reason = "Google Calendar access requires reauthorization. Please reconnect your Google account."
                req_reauth = True
            else:
                clean_reason = err_str
                req_reauth = False
            sections["today_events"] = {
                "available": False,
                "reason": clean_reason,
                "requires_reauth": req_reauth,
                "count": 0,
                "items": [],
                "conflicts": [],
            }

        # --- Overdue tasks --------------------------------------------------
        try:
            task_view = task_agent.run(agent_ctx, TaskViewInput()).output
            overdue_raw = task_view.overdue
            overdue_items = []
            for t in overdue_raw:
                due_dt = parse_email_datetime(t.get("due_date"), user_tz)
                overdue_days = max(1, (now_local.date() - due_dt.date()).days) if due_dt else 1
                overdue_items.append({
                    "id": t.get("id"),
                    "title": t.get("title"),
                    "description": t.get("description", ""),
                    "due_date": t.get("due_date"),
                    "priority": t.get("priority", "medium"),
                    "status": t.get("status", "pending"),
                    "overdue_days": overdue_days,
                })

            priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
            overdue_items.sort(key=lambda x: (priority_order.get(x.get("priority", "medium"), 2), -x.get("overdue_days", 1)))

            sections["overdue_tasks"] = {
                "available": True,
                "count": len(overdue_items),
                "items": overdue_items,
            }
        except Exception as exc:
            sections["overdue_tasks"] = {"available": False, "reason": str(exc), "count": 0, "items": []}

        # --- Upcoming deadlines (Due Today, 3 Days, 7 Days) ----------------
        try:
            task_view = task_agent.run(agent_ctx, TaskViewInput()).output
            all_tasks = task_view.tasks
            soon_3d = day_end + timedelta(days=3)
            soon_7d = day_end + timedelta(days=7)

            due_today_tasks = []
            upcoming_3d_tasks = []
            upcoming_7d_tasks = []

            for t in all_tasks:
                due_raw = t.get("due_date")
                if not due_raw or t.get("status") in ("done", "cancelled"):
                    continue
                due_dt = parse_email_datetime(due_raw, user_tz)
                if not due_dt:
                    continue
                if day_start <= due_dt < day_end:
                    due_today_tasks.append(t)
                elif day_end <= due_dt < soon_3d:
                    upcoming_3d_tasks.append(t)
                elif soon_3d <= due_dt < soon_7d:
                    upcoming_7d_tasks.append(t)

            # Keep legacy upcoming_deadlines key matching due in next 3 days
            sections["upcoming_deadlines"] = {
                "available": True,
                "count": len(upcoming_3d_tasks),
                "items": upcoming_3d_tasks,
                "due_today": due_today_tasks,
                "within_3_days": upcoming_3d_tasks,
                "within_7_days": upcoming_7d_tasks,
            }
        except Exception as exc:
            sections["upcoming_deadlines"] = {"available": False, "reason": str(exc), "count": 0, "items": []}

        # --- At-risk commitments (Commitment Tracker) ----------------------
        try:
            all_commits = commitment_service.list_commitments(db, owner_id)
            at_risk = []
            for c in all_commits:
                if c.status == "at_risk":
                    at_risk.append(c)
                elif c.status != "completed" and c.due_date:
                    due_dt = parse_email_datetime(c.due_date, user_tz)
                    if due_dt and due_dt < day_start:
                        at_risk.append(c)

            formatted_at_risk = [
                {
                    "id": c.id,
                    "description": c.description,
                    "due_date": c.due_date,
                    "responsible_party": c.responsible_party,
                    "owner": c.responsible_party or "User",
                    "status": c.status,
                    "risk_reason": "Deadline passed" if c.due_date and str(c.due_date) < day_start.date().isoformat() else "Commitment flagged at risk",
                    "priority": "high",
                }
                for c in at_risk
            ]

            sections["at_risk_commitments"] = {
                "available": True,
                "count": len(formatted_at_risk),
                "items": formatted_at_risk,
            }
        except Exception as exc:
            sections["at_risk_commitments"] = {"available": False, "reason": str(exc), "count": 0, "items": []}

        # Suggested actions & AI summary
        sections["suggested_actions"] = _suggested_actions(sections)
        ai_summary = _generate_ai_summary(sections, user_tz)

        # Overview counts
        overview = {
            "total_unread": sections.get("unread_email", {}).get("total_unread", sections.get("unread_email", {}).get("count", 0)),
            "important_emails": sections.get("unread_email", {}).get("important", 0),
            "overdue_tasks": sections.get("overdue_tasks", {}).get("count", 0),
            "today_events": sections.get("today_events", {}).get("count", 0),
        }

        # Source statuses
        gmail_avail = sections.get("unread_email", {}).get("available", False)
        cal_avail = sections.get("today_events", {}).get("available", False)
        cal_reauth = sections.get("today_events", {}).get("requires_reauth", False)
        source_status = {
            "gmail": "connected" if gmail_avail else "disconnected",
            "calendar": "connected" if cal_avail else ("reconnect_required" if cal_reauth else "disconnected"),
            "tasks": "connected",
        }

        return {
            "result": {
                "date": now_local.strftime("%Y-%m-%d"),
                "timezone": user_tz,
                "generated_at": now_local.isoformat(),
                "owner_id": owner_id,
                "overview": overview,
                "summary": _render_digest_text(sections),
                "ai_summary": ai_summary,
                "emails": {
                    "today": emails_today if "emails_today" in locals() else [],
                    "yesterday": emails_yesterday if "emails_yesterday" in locals() else [],
                    "older": emails_older if "emails_older" in locals() else [],
                    "important": emails_important if "emails_important" in locals() else [],
                    "counts": {
                        "urgent": sections.get("unread_email", {}).get("urgent", 0),
                        "needs_reply": sections.get("unread_email", {}).get("needs_reply", 0),
                        "fyi": sections.get("unread_email", {}).get("fyi", 0),
                        "spam": sections.get("unread_email", {}).get("spam", 0),
                    },
                    "total_unread": sections.get("unread_email", {}).get("total_unread", 0),
                    "fetched_count": sections.get("unread_email", {}).get("fetched_count", 0),
                    "has_more": sections.get("unread_email", {}).get("has_more", False),
                    "next_page_token": sections.get("unread_email", {}).get("next_page_token"),
                    "items": sections.get("unread_email", {}).get("items", []),
                },
                "calendar": {
                    "events": sections.get("today_events", {}).get("items", []),
                    "total": sections.get("today_events", {}).get("count", 0),
                    "next_event": sections.get("today_events", {}).get("next_event"),
                    "conflicts": sections.get("today_events", {}).get("conflicts", []),
                    "requires_reauth": sections.get("today_events", {}).get("requires_reauth", False),
                },
                "tasks": {
                    "overdue": sections.get("overdue_tasks", {}).get("items", []),
                    "due_today": sections.get("upcoming_deadlines", {}).get("due_today", []),
                    "upcoming": sections.get("upcoming_deadlines", {}).get("within_3_days", []),
                },
                "commitments": {
                    "at_risk": sections.get("at_risk_commitments", {}).get("items", []),
                },
                "source_status": source_status,
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
        raw_extract = inbox_agent.extract_commitments(
            list(messages),
            execution_mode=context.execution_mode,
            timeout=context.timeout,
            request_id=context.request_id,
        )
        if isinstance(raw_extract, dict) and "commitments" in raw_extract:
            gmail_commitments = raw_extract["commitments"]
            extraction_res = raw_extract
        else:
            gmail_commitments = raw_extract if isinstance(raw_extract, list) else []
            extraction_res = getattr(inbox_agent, "_last_telemetry", {}) or {}

        created = 0
        updated = 0

        for item in gmail_commitments:
            _, was_created = commitment_service.upsert_commitment(
                db=db, owner_id=owner_id,
                description=item["description"],
                source_type="gmail",
                source_ref=item["id"],
                responsible_party=item.get("owner") or item.get("responsible_party"),
                counterparty=item.get("counterparty"),
                direction=item.get("direction", "owed_by_me"),
                due_date=item.get("due_date"),
                evidence=item.get("evidence"),
                confidence=item.get("confidence", 0.9),
                priority=item.get("priority", "medium"),
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
                "total_messages": extraction_res.get("total_messages", len(messages)),
                "processed_messages": extraction_res.get("processed_messages", len(messages)),
                "successful_messages": extraction_res.get("successful_messages", len(messages)),
                "no_commitment_messages": extraction_res.get("no_commitment_messages", 0),
                "failed_messages": extraction_res.get("failed_messages", 0),
                "commitments_found": len(gmail_commitments) + len(action_items),
                "status": extraction_res.get("status", "completed"),
                "warnings": extraction_res.get("warnings", []),
                "errors": extraction_res.get("errors", []),
            },
            "provider": "commitment_service",
            "model": None,
        }
