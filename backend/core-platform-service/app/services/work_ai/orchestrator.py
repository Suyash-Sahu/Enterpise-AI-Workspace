"""
AMOF Work orchestrator (PRD v3 §6.1): the only component allowed to route an
agent's output toward execution -- and "toward execution" always means
pipeline.create_proposal(). It never mutates WorkGraph itself.

    Agent output -> AI Proposal -> Approval / Autonomy Policy -> Execution -> Audit

Read-only agent results (focus plan, risk radar) are returned directly: they
change nothing, so there is nothing to approve.
"""
import logging
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.base import AgentContext
from app.agents.work_agents import (
    CaptureInput, DuplicateInput, FocusInput, RiskInput, SprintInput, work_agent_registry,
)
from app.models.work_ai import AiProposal
from app.schemas.execution import ExecutionRequest
from app.services.commitment_service import commitment_service
from app.services.execution_manager import execution_manager
from app.services.work_ai import pipeline
from app.services.workgraph_service import workgraph_service

logger = logging.getLogger(__name__)

# Where capture text may come from. Anything other than the signed-in user's own
# command is untrusted content (PRD §10); it may still become a *proposal*, but
# it can never auto-execute, even under an L3 grant.
CAPTURE_SOURCES = ("user_command", "email", "meeting", "comment", "document")
_AUTO_EXECUTE_SOURCES = ("user_command",)
_MAX_RISK_ALERTS_PER_SCAN = 20
_MAX_SWEEP_COMMITMENTS = 15  # ponytail: bound per-call cost; page/paginate if this becomes a real bottleneck
_SWEEPABLE_COMMITMENT_STATUSES = ("pending", "at_risk")


def _run(db: Session, owner_id: str, agent: str, inputs: Any):
    return work_agent_registry.get_agent(agent).run(AgentContext(owner_id=owner_id, db=db), inputs)


def _check_project(db: Session, owner_id: str, project_id: Optional[str]) -> None:
    if project_id and workgraph_service.get_project(db, owner_id, project_id) is None:
        raise ValueError("Project not found.")


# ------------------------------------------------------------------ Smart Capture

def capture(
    db: Session,
    owner_id: str,
    text: str,
    *,
    source: str = "user_command",
    source_ref: Optional[str] = None,
    project_id: Optional[str] = None,
    user_email: Optional[str] = None,
    use_llm: Optional[bool] = None,
    type_hint: Optional[str] = None,
) -> dict[str, Any]:
    """Free text -> create_item proposal (+ a duplicate warning when one is likely). Never creates the item."""
    if source not in CAPTURE_SOURCES:
        raise ValueError(f"Unknown capture source '{source}'.")
    _check_project(db, owner_id, project_id)

    draft = _run(db, owner_id, "CaptureAgent",
                 CaptureInput(text=text, source=source, project_id=project_id, user_email=user_email, use_llm=use_llm)).output
    if type_hint in ("BUG", "FEATURE") and draft.type == "TASK":
        draft.type = type_hint
    dup = _run(db, owner_id, "DuplicateAgent", DuplicateInput(title=draft.title, project_id=project_id)).output

    payload = {k: v for k, v in {
        "title": draft.title, "description": draft.description, "priority": draft.priority, "type": draft.type,
        "due_date": draft.due_date, "assignee": draft.assignee, "project_id": project_id,
    }.items() if v is not None}
    notes = "; ".join(draft.notes)
    prop = pipeline.create_proposal(
        db, owner_id, kind="create_item", payload=payload, agent="capture", source=source, source_ref=source_ref,
        confidence=draft.confidence,
        explanation=f"Drafted from {source.replace('_', ' ')} ({draft.method} parse)." + (f" {notes}" if notes else ""),
        # never auto-run from untrusted text, nor when a duplicate is suspected
        allow_auto=source in _AUTO_EXECUTE_SOURCES and not dup.is_possible_duplicate,
    )

    warning = None
    if dup.is_possible_duplicate:
        warning = pipeline.create_proposal(
            db, owner_id, kind="duplicate_warning", agent="duplicate", source=source, source_ref=prop.id,
            confidence=dup.matches[0].score,
            explanation=f"'{draft.title}' looks like an existing item. Nothing is merged automatically.",
            payload={"title": draft.title, "project_id": project_id, "related_proposal": prop.id,
                     "matches": [m.model_dump() for m in dup.matches]},
            allow_auto=False,
        )
    return {"proposal": prop, "duplicate_warning": warning, "draft": draft}


# ------------------------------------------------------------------ read-only agents

def focus_plan(db: Session, owner_id: str, *, project_id: Optional[str] = None, limit: int = 7,
               user_email: Optional[str] = None):
    _check_project(db, owner_id, project_id)
    return _run(db, owner_id, "FocusAgent", FocusInput(project_id=project_id, limit=limit, user_email=user_email)).output


def risks(db: Session, owner_id: str, *, project_id: Optional[str] = None):
    _check_project(db, owner_id, project_id)
    return _run(db, owner_id, "RiskAgent", RiskInput(project_id=project_id)).output


def scan_risks(db: Session, owner_id: str, *, project_id: Optional[str] = None) -> list[AiProposal]:
    """Publish high/medium risks to the AI Inbox as informational alerts (deduped against open ones)."""
    report = risks(db, owner_id, project_id=project_id)
    open_alerts = {
        (p.payload.get("task_id"), p.payload.get("risk_type"))
        for p in pipeline.list_proposals(db, owner_id, status="PENDING", kind="risk_alert", limit=200)
    }
    created: list[AiProposal] = []
    for r in report.risks:
        if r.severity == "low" or (r.task_id, r.type) in open_alerts:
            continue
        if len(created) >= _MAX_RISK_ALERTS_PER_SCAN:
            break
        created.append(pipeline.create_proposal(
            db, owner_id, kind="risk_alert", agent="risk", source="risk_scan", source_ref=r.task_id,
            explanation=r.detail, allow_auto=False,
            payload={"task_id": r.task_id, "title": r.title, "risk_type": r.type, "severity": r.severity,
                     "detail": r.detail, "project_id": r.project_id},
        ))
    return created


def sprint_plan(db: Session, owner_id: str, *, capacity: int = 5, project_id: Optional[str] = None) -> AiProposal:
    """Proposal-only: an informational plan in the inbox. No sprint entity exists or is created."""
    _check_project(db, owner_id, project_id)
    plan = _run(db, owner_id, "SprintPlanningAgent", SprintInput(capacity=capacity, project_id=project_id)).output
    return pipeline.create_proposal(
        db, owner_id, kind="sprint_plan", agent="sprint", source="planning", allow_auto=False,
        explanation=f"Suggested {len(plan.items)} item(s) for the next cycle (capacity {plan.capacity}). "
                    "Approving only acknowledges the suggestion; nothing is scheduled or changed.",
        payload={**plan.model_dump(), "project_id": project_id},
    )


# ------------------------------------------------------------------ Commitment Sweep

def commitment_sweep(db: Session, owner_id: str, *, max_emails: int = 10, user_email: Optional[str] = None) -> dict:
    """
    One visible autonomous loop over agents that already exist, chained rather
    than reinvented: rescan the inbox for commitments (commitment.scan) -> draft
    a task proposal for each unresolved one via capture() (CaptureAgent +
    DuplicateAgent, same as Smart Capture) -> re-scan risk via scan_risks().

    The commitment tracker itself stays read/track-only (commitment_service.py's
    own invariant: "nothing here creates a WorkGraph task"); this only reads its
    output and proposes through the existing, already-approval-gated path. A
    commitment sourced from "email" can never auto-execute (see
    _AUTO_EXECUTE_SOURCES), so every draft this produces still waits in the AI
    Inbox for a human decision.
    """
    scan_res = execution_manager.execute(
        db=db,
        request=ExecutionRequest(task_type="commitment.scan", input={"max_emails": max_emails}),
        owner_id=owner_id,
    )
    if scan_res.status.value != "COMPLETED" or not scan_res.result:
        raise ValueError(scan_res.error_message or "Commitment scan failed.")

    scan_summary = {
        "scanned_gmail": scan_res.result.get("scanned_gmail", 0),
        "scanned_meeting_items": scan_res.result.get("scanned_meeting_items", 0),
        "created": scan_res.result.get("created", 0),
        "updated": scan_res.result.get("updated", 0),
    }
    steps = [{
        "step": "scan", "label": "Scanned inbox for commitments",
        "detail": (
            f"{scan_summary['scanned_gmail']} email(s), {scan_summary['scanned_meeting_items']} meeting item(s) "
            f"scanned; {scan_summary['created']} new, {scan_summary['updated']} updated."
        ),
        "count": scan_summary["created"] + scan_summary["updated"],
    }]

    candidates = [
        c for c in commitment_service.list_commitments(db, owner_id)
        if c.status in _SWEEPABLE_COMMITMENT_STATUSES and c.linked_task_id is None
    ][:_MAX_SWEEP_COMMITMENTS]
    already_proposed = {
        p.source_ref for p in pipeline.list_proposals(db, owner_id, status="PENDING", kind="create_item", limit=200)
    }

    proposals_created = duplicate_warnings = skipped = 0
    for c in candidates:
        if c.id in already_proposed:
            skipped += 1
            continue
        capture_source = "meeting" if c.source_type == "meeting" else "email"
        result = capture(db, owner_id, c.description, source=capture_source, source_ref=c.id, user_email=user_email)
        proposals_created += 1
        if result["duplicate_warning"] is not None:
            duplicate_warnings += 1

    steps.append({
        "step": "draft", "label": "Drafted task proposals from commitments",
        "detail": (
            f"{proposals_created} proposal(s) drafted, {duplicate_warnings} possible duplicate(s) flagged, "
            f"{skipped} already proposed and skipped."
            if candidates else "No unresolved commitments to draft."
        ),
        "count": proposals_created,
    })

    risk_alerts = scan_risks(db, owner_id)
    steps.append({
        "step": "risk_scan", "label": "Scanned WorkGraph for risk",
        "detail": (
            f"{len(risk_alerts)} new risk alert(s) published to the AI Inbox." if risk_alerts else "No new risk alerts."
        ),
        "count": len(risk_alerts),
    })

    return {
        "steps": steps,
        "scan": scan_summary,
        "proposals_created": proposals_created,
        "duplicate_warnings": duplicate_warnings,
        "risk_alerts_created": len(risk_alerts),
        "skipped_already_proposed": skipped,
    }
