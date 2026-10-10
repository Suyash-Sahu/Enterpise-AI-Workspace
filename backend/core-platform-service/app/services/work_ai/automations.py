"""
AMOF Work rule-based automations (PRD v3 §7.1).

  rule = trigger + conditions + actions  (validated, structured, never free text)

Lifecycle: draft -> preview (dry-run of the exact current definition) -> active
<-> paused. Activation without a matching preview is refused server-side.

A run never writes WorkGraph. Each matched item goes through the AutomationAgent
(read-only: rule actions -> proposal drafts) and then pipeline.create_proposal(),
so a rule's actions are proposals under the same Approval/Autonomy policy as
everything else: L1 (pending in the AI Inbox) by default, auto-applied only where
the owner granted L3 for that (project, kind). There is no separate execution path.

Safety (all enforced here, all fail closed, all audited):
  * tenant: every query is scoped by the rule's owner_id
  * kill switch: checked before the run and again before EACH item; an in-flight
    item is never aborted, the next checkpoint stops the run
  * blast radius: more than WORK_AUTOMATION_MAX_ITEMS_PER_RUN matches => nothing runs
  * rate limit: at most WORK_AUTOMATION_MAX_RUNS_PER_HOUR runs per rule per hour
  * loop protection: activity caused by any `agent:*` actor (automations, AI
    proposals, approved AI changes) never triggers a rule, and a (rule, item,
    trigger occurrence) fires at most once
Time-based/event evaluation is driven by ONE Celery beat entry (work_automations_tick)
that reuses the existing Celery app; event triggers read the activity log.
"""
import hashlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.base import AgentContext
from app.agents.work_agents import ActionSpec, AutomationPlanInput, work_agent_registry
from app.core.config import settings
from app.models.work_ai import WorkAutomation, WorkAutomationFired, WorkAutomationRun
from app.models.workgraph import Task, WorkItemActivity
from app.services.work_ai import guard, pipeline
from app.services.workgraph_service import workgraph_service

logger = logging.getLogger(__name__)

Status = Literal["backlog", "open", "todo", "in_progress", "in_review", "blocked", "done", "cancelled"]
Priority = Literal["low", "medium", "high", "urgent"]
WType = Literal["TASK", "BUG", "FEATURE"]
STATUSES = ("backlog", "open", "todo", "in_progress", "in_review", "blocked", "done", "cancelled")
PRIORITIES = ("low", "medium", "high", "urgent")
CLOSED = ("done", "cancelled")
MAX_RULES_PER_OWNER = 50
_MAX_EVENTS_PER_SCAN = 1000
_PREVIEW_LOOKBACK_DAYS = 7
_PREVIEW_LIST = 25


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# =========================================================================== definition

class Trigger(BaseModel):
    type: Literal["item_created", "status_changed", "priority_changed", "overdue"]
    to: Optional[str] = None

    @model_validator(mode="after")
    def _check(self):
        if self.type == "status_changed" and self.to not in STATUSES:
            raise ValueError(f"status_changed needs 'to' to be one of {STATUSES}")
        if self.type == "priority_changed" and self.to not in PRIORITIES:
            raise ValueError(f"priority_changed needs 'to' to be one of {PRIORITIES}")
        if self.type in ("item_created", "overdue") and self.to is not None:
            raise ValueError(f"{self.type} takes no 'to'")
        return self


class Conditions(BaseModel):
    priority: list[Priority] = Field(default_factory=list, max_length=4)
    status: list[Status] = Field(default_factory=list, max_length=8)
    type: list[WType] = Field(default_factory=list, max_length=3)
    unassigned: bool = False


class Action(BaseModel):
    type: Literal["set_priority", "set_status", "assign", "create_followup", "notify"]
    value: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def _check(self):
        v = (self.value or "").strip()
        if self.type == "set_priority" and v not in PRIORITIES:
            raise ValueError(f"set_priority needs a value in {PRIORITIES}")
        if self.type == "set_status" and v not in STATUSES:
            raise ValueError(f"set_status needs a value in {STATUSES}")
        if self.type == "assign" and not v:
            raise ValueError("assign needs a value")
        self.value = v or None
        return self


class RuleDefinition(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    project_id: Optional[str] = None
    trigger: Trigger
    conditions: Conditions = Field(default_factory=Conditions)
    actions: list[Action] = Field(min_length=1, max_length=5)

    @field_validator("name")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip() or "Untitled rule"


def definition_hash(project_id: Optional[str], trigger: dict, conditions: dict, actions: list) -> str:
    canon = json.dumps({"p": project_id, "t": trigger, "c": conditions, "a": actions}, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode()).hexdigest()


def _hash_of(defn: RuleDefinition) -> str:
    return definition_hash(defn.project_id, defn.trigger.model_dump(mode="json"),
                           defn.conditions.model_dump(mode="json"), [a.model_dump(mode="json") for a in defn.actions])


# =========================================================================== matching

class Match:
    def __init__(self, task: Task, key: str, cursor_id: int = 0):
        self.task, self.key, self.cursor_id = task, key, cursor_id


def _cond_ok(t: Task, c: dict) -> bool:
    if c.get("priority") and t.priority not in c["priority"]:
        return False
    if c.get("status") and t.status not in c["status"]:
        return False
    if c.get("type") and (t.type or "TASK") not in c["type"]:
        return False
    if c.get("unassigned") and t.assignee:
        return False
    return True


def _scan(db: Session, owner_id: str, project_id: Optional[str], trigger: dict, cond: dict, *,
          cursor: Optional[int] = None, since: Optional[datetime] = None, now: Optional[datetime] = None
          ) -> tuple[list[Match], int]:
    """Owner-scoped candidates for a trigger. Returns (matches, highest activity id examined)."""
    now = now or _now()
    ttype = trigger["type"]
    if ttype == "overdue":
        q = db.query(Task).filter(Task.owner_id == owner_id, Task.due_date.isnot(None), Task.due_date < now,
                                  Task.status.notin_(CLOSED))
        if project_id:
            q = q.filter(Task.project_id == project_id)
        return ([Match(t, f"overdue:{t.due_date.isoformat()}") for t in q.limit(5000) if _cond_ok(t, cond)],
                cursor or 0)

    q = db.query(WorkItemActivity).filter(WorkItemActivity.owner_id == owner_id)
    if cursor is not None:
        q = q.filter(WorkItemActivity.id > cursor)
    if since is not None:
        q = q.filter(WorkItemActivity.created_at >= since)
    events = q.order_by(WorkItemActivity.id).limit(_MAX_EVENTS_PER_SCAN).all()
    top = events[-1].id if events else (cursor or 0)

    wanted: list[WorkItemActivity] = []
    for ev in events:
        if (ev.actor or "").startswith("agent:"):
            continue  # loop protection: AI/automation-caused changes never trigger rules
        changes = (ev.payload or {}).get("changes", {}) if isinstance(ev.payload, dict) else {}
        if ttype == "item_created" and ev.event_type == "created":
            wanted.append(ev)
        elif ttype == "status_changed" and ev.event_type in ("status_changed", "updated") \
                and (changes.get("status") or {}).get("to") == trigger.get("to"):
            wanted.append(ev)
        elif ttype == "priority_changed" and ev.event_type == "updated" \
                and (changes.get("priority") or {}).get("to") == trigger.get("to"):
            wanted.append(ev)
    if not wanted:
        return [], top
    tasks = {t.id: t for t in db.query(Task).filter(Task.owner_id == owner_id,
                                                    Task.id.in_({e.task_id for e in wanted}))}
    out = []
    for ev in wanted:
        t = tasks.get(ev.task_id)
        if t is None or (project_id and t.project_id != project_id) or not _cond_ok(t, cond):
            continue
        out.append(Match(t, f"act:{ev.id}", ev.id))
    return out, top


def _unfired(db: Session, automation_id: str, matches: list[Match]) -> list[Match]:
    if not matches:
        return []
    done = {(r.task_id, r.trigger_key) for r in db.query(WorkAutomationFired).filter(
        WorkAutomationFired.automation_id == automation_id,
        WorkAutomationFired.task_id.in_({m.task.id for m in matches}))}
    return [m for m in matches if (m.task.id, m.key) not in done]


def _plan(db: Session, owner_id: str, actions: list[dict], task: Task):
    agent = work_agent_registry.get_agent("AutomationAgent")
    out = agent.run(AgentContext(owner_id=owner_id, db=db), AutomationPlanInput(
        actions=[ActionSpec(**a) for a in actions], task_id=task.id, task_title=task.title, project_id=task.project_id)).output
    drafts = []
    for d in out.drafts:
        if d.kind == "update_item":  # skip no-ops (e.g. set_priority to what it already is)
            field, value = next((k, v) for k, v in d.payload.items() if k != "task_id")
            if getattr(task, field) == value:
                continue
        drafts.append(d)
    return drafts


# =========================================================================== CRUD / lifecycle

def _audit(db: Session, owner_id: str, action: str) -> None:
    guard._audit(db, owner_id, action)


def create_rule(db: Session, owner_id: str, defn: RuleDefinition, source_text: Optional[str] = None) -> WorkAutomation:
    if defn.project_id and workgraph_service.get_project(db, owner_id, defn.project_id) is None:
        raise ValueError("Project not found.")
    if db.query(func.count(WorkAutomation.id)).filter(WorkAutomation.owner_id == owner_id).scalar() >= MAX_RULES_PER_OWNER:
        raise ValueError(f"Rule limit reached ({MAX_RULES_PER_OWNER}).")
    rule = WorkAutomation(
        owner_id=owner_id, project_id=defn.project_id, name=defn.name, source_text=(source_text or "")[:1000] or None,
        trigger=defn.trigger.model_dump(mode="json"), conditions=defn.conditions.model_dump(mode="json"),
        actions=[a.model_dump(mode="json") for a in defn.actions], status="draft", definition_hash=_hash_of(defn),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    _audit(db, owner_id, f"work.automation.create:{rule.id}")
    return rule


def get_rule(db: Session, owner_id: str, rule_id: str) -> Optional[WorkAutomation]:
    return db.query(WorkAutomation).filter(WorkAutomation.id == rule_id, WorkAutomation.owner_id == owner_id).first()


def list_rules(db: Session, owner_id: str) -> list[WorkAutomation]:
    return db.query(WorkAutomation).filter(WorkAutomation.owner_id == owner_id).order_by(WorkAutomation.created_at.desc()).all()


def list_runs(db: Session, owner_id: str, rule_id: str, limit: int = 20) -> list[WorkAutomationRun]:
    if get_rule(db, owner_id, rule_id) is None:
        raise LookupError("Automation not found.")
    return (db.query(WorkAutomationRun).filter(WorkAutomationRun.owner_id == owner_id, WorkAutomationRun.automation_id == rule_id)
            .order_by(WorkAutomationRun.id.desc()).limit(max(1, min(limit, 100))).all())


def dry_run(db: Session, owner_id: str, project_id: Optional[str], trigger: dict, conditions: dict, actions: list[dict],
            *, rule_id: Optional[str] = None) -> dict[str, Any]:
    """Read-only: what this rule would match and propose right now. Writes nothing."""
    if project_id and workgraph_service.get_project(db, owner_id, project_id) is None:
        raise ValueError("Project not found.")
    since = None if trigger["type"] == "overdue" else _now() - timedelta(days=_PREVIEW_LOOKBACK_DAYS)
    matches, _ = _scan(db, owner_id, project_id, trigger, conditions, since=since)
    if rule_id:
        matches = _unfired(db, rule_id, matches)
    cap = settings.WORK_AUTOMATION_MAX_ITEMS_PER_RUN
    sample = []
    for m in matches[:_PREVIEW_LIST]:
        drafts = []
        for d in _plan(db, owner_id, actions, m.task):
            level = guard.effective_level(db, owner_id, m.task.project_id, d.kind) if d.kind in guard.MUTATING_KINDS else "n/a"
            drafts.append({"kind": d.kind, "payload": d.payload, "explanation": d.explanation, "autonomy_level": level,
                           "would_auto_execute": level == "L3" and guard.l3_eligible(d.kind)})
        sample.append({"task_id": m.task.id, "title": m.task.title, "status": m.task.status,
                       "priority": m.task.priority, "drafts": drafts})
    warnings = []
    if len(matches) > cap:
        warnings.append(f"{len(matches)} items match, more than the safety limit of {cap}: a real run would be BLOCKED and change nothing.")
    if not matches:
        warnings.append("Nothing matches right now"
                        + ("" if trigger["type"] == "overdue" else f" (looked at the last {_PREVIEW_LOOKBACK_DAYS} days of activity)") + ".")
    if any(d["would_auto_execute"] for s in sample for d in s["drafts"]):
        warnings.append("Some actions would be applied automatically because you granted L3 for that project and action.")
    else:
        warnings.append("Actions become proposals in your AI Inbox for approval; nothing is applied automatically.")
    return {"total_matched": len(matches), "max_items_per_run": cap, "would_exceed_limit": len(matches) > cap,
            "sample": sample, "warnings": warnings, "kill_switch_on": guard.is_enabled(db, owner_id, project_id)}


def preview_rule(db: Session, owner_id: str, rule_id: str) -> dict[str, Any]:
    rule = get_rule(db, owner_id, rule_id)
    if rule is None:
        raise LookupError("Automation not found.")
    result = dry_run(db, owner_id, rule.project_id, rule.trigger, rule.conditions, rule.actions, rule_id=rule.id)
    rule.previewed_hash = rule.definition_hash
    rule.previewed_at = datetime.now(timezone.utc)
    db.commit()
    _audit(db, owner_id, f"work.automation.preview:{rule.id}")
    return result


def _max_activity_id(db: Session, owner_id: str) -> int:
    return db.query(func.coalesce(func.max(WorkItemActivity.id), 0)).filter(WorkItemActivity.owner_id == owner_id).scalar() or 0


def activate(db: Session, owner_id: str, rule_id: str, *, resume: bool = False) -> WorkAutomation:
    rule = get_rule(db, owner_id, rule_id)
    if rule is None:
        raise LookupError("Automation not found.")
    if rule.status == "active":
        return rule
    if resume and rule.status != "paused":
        raise ValueError("Only a paused automation can be resumed.")
    if not resume and rule.status != "draft":
        raise ValueError("Only a draft automation can be activated; resume a paused one.")
    if rule.previewed_hash != rule.definition_hash:
        raise PermissionError("Preview this automation (dry-run) before activating it.")
    rule.status = "active"
    rule.activated_at = datetime.now(timezone.utc)
    rule.cursor = _max_activity_id(db, owner_id)  # only future events; nothing from before activation/pause fires
    db.commit()
    _audit(db, owner_id, f"work.automation.{'resume' if resume else 'activate'}:{rule.id}")
    return rule


def pause(db: Session, owner_id: str, rule_id: str) -> WorkAutomation:
    rule = get_rule(db, owner_id, rule_id)
    if rule is None:
        raise LookupError("Automation not found.")
    if rule.status != "active":
        raise ValueError("Only an active automation can be paused.")
    rule.status = "paused"
    db.commit()
    _audit(db, owner_id, f"work.automation.pause:{rule.id}")
    return rule


# =========================================================================== execution

def _record(db: Session, rule: WorkAutomation, status: str, matched: int = 0, *, detail: Optional[dict] = None,
            error: Optional[str] = None, dedupe_hours: Optional[float] = None) -> Optional[WorkAutomationRun]:
    if dedupe_hours:  # don't write the same refusal every tick
        last = (db.query(WorkAutomationRun).filter(WorkAutomationRun.automation_id == rule.id)
                .order_by(WorkAutomationRun.id.desc()).first())
        if last and last.status == status and last.started_at:
            started = last.started_at if last.started_at.tzinfo else last.started_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - started < timedelta(hours=dedupe_hours):
                return None
    run = WorkAutomationRun(automation_id=rule.id, owner_id=rule.owner_id, status=status, matched_count=matched,
                            detail=detail, error=error, finished_at=datetime.now(timezone.utc))
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_rule(db: Session, rule: WorkAutomation, now: Optional[datetime] = None) -> Optional[WorkAutomationRun]:
    """Evaluate one active rule. Returns the run row if the evaluation found work (or was refused)."""
    if rule.status != "active":
        return None
    now = now or _now()
    owner = rule.owner_id
    cap, per_hour = settings.WORK_AUTOMATION_MAX_ITEMS_PER_RUN, settings.WORK_AUTOMATION_MAX_RUNS_PER_HOUR

    if not guard.is_enabled(db, owner, rule.project_id):
        return _record(db, rule, "halted_kill_switch", detail={"reason": "AI Work Automation is OFF"}, dedupe_hours=1)

    is_event = rule.trigger["type"] != "overdue"
    matches, top = _scan(db, owner, rule.project_id, rule.trigger, rule.conditions,
                         cursor=rule.cursor if is_event else None, now=now)
    matches = _unfired(db, rule.id, matches)
    if not matches:
        if is_event and top > rule.cursor:
            rule.cursor = top
            db.commit()
        return None

    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = db.query(func.count(WorkAutomationRun.id)).filter(
        WorkAutomationRun.automation_id == rule.id, WorkAutomationRun.started_at >= since,
        WorkAutomationRun.status.in_(("completed", "partial", "blocked_blast_radius"))).scalar() or 0
    if recent >= per_hour:  # cursor NOT advanced: the matches run once the window frees up
        return _record(db, rule, "rate_limited", len(matches), detail={"limit_per_hour": per_hour}, dedupe_hours=1)

    if len(matches) > cap:  # fail closed: nothing executes, and the refusal is auditable
        for m in matches:
            db.add(WorkAutomationFired(automation_id=rule.id, task_id=m.task.id, trigger_key=m.key, outcome="blocked"))
        if is_event:
            rule.cursor = max(rule.cursor, top)
        db.commit()
        _audit(db, owner, f"work.automation.blocked:{rule.id}:{len(matches)}>{cap}")
        return _record(db, rule, "blocked_blast_radius", len(matches),
                       detail={"max_items_per_run": cap, "items": [m.task.id for m in matches[:50]]})

    run = WorkAutomationRun(automation_id=rule.id, owner_id=owner, status="completed", matched_count=len(matches))
    db.add(run)
    db.commit()
    db.refresh(run)
    made = executed = 0
    errors: list[str] = []
    processed: list[str] = []
    halted = False
    last_cursor = rule.cursor
    for m in matches:
        try:
            guard.assert_enabled(db, owner, m.task.project_id)  # checkpoint before EACH item
        except guard.KillSwitchOff:
            halted = True
            break
        outcome = "proposed"
        try:
            for d in _plan(db, owner, rule.actions, m.task):
                prop = pipeline.create_proposal(
                    db, owner, kind=d.kind, payload=d.payload, agent="automation", source="automation", source_ref=rule.id,
                    explanation=f"Rule '{rule.name}': {d.explanation}", allow_auto=True)
                made += 1
                if prop.status == "EXECUTED":
                    executed += 1
                    outcome = "executed"
        except guard.KillSwitchOff:
            halted = True
            break
        except Exception as exc:  # noqa: BLE001 - one bad item must not sink the run
            db.rollback()
            errors.append(f"{m.task.id}: {type(exc).__name__}: {exc}"[:300])
            outcome = "error"
        db.add(WorkAutomationFired(automation_id=rule.id, task_id=m.task.id, trigger_key=m.key, outcome=outcome))
        db.commit()
        processed.append(m.task.id)
        last_cursor = max(last_cursor, m.cursor_id)

    if is_event:
        rule.cursor = last_cursor if halted else max(rule.cursor, top)
    run.proposals_created, run.executed_count = made, executed
    run.status = "halted_kill_switch" if halted else ("partial" if errors else "completed")
    run.detail = {"items": processed[:50], "errors": errors[:10]}
    run.error = errors[0] if errors else None
    run.finished_at = datetime.now(timezone.utc)
    db.commit()
    return run


def run_now(db: Session, owner_id: str, rule_id: str) -> Optional[WorkAutomationRun]:
    rule = get_rule(db, owner_id, rule_id)
    if rule is None:
        raise LookupError("Automation not found.")
    if rule.status != "active":
        raise ValueError("Automation is not active.")
    return run_rule(db, rule)


def tick(db: Session, now: Optional[datetime] = None) -> dict[str, int]:
    """Evaluate every active rule (called by the Celery beat task). One failing rule never stops the rest."""
    summary = {"rules": 0, "runs": 0, "failed": 0}
    for rule in db.query(WorkAutomation).filter(WorkAutomation.status == "active").all():
        summary["rules"] += 1
        try:
            if run_rule(db, rule, now):
                summary["runs"] += 1
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            summary["failed"] += 1
            logger.exception("[WorkAutomation] rule %s failed", rule.id)
            _record(db, rule, "failed", error=f"{type(exc).__name__}: {exc}"[:500], dedupe_hours=1)
    return summary


# =========================================================================== NL rule builder

class RuleDraft(BaseModel):
    needs_clarification: bool = False
    clarification: Optional[str] = None
    definition: Optional[RuleDefinition] = None
    warnings: list[str] = Field(default_factory=list)


_STATUS_MAP = {
    "done": "done", "completed": "done", "complete": "done", "finished": "done", "blocked": "blocked",
    "in progress": "in_progress", "in review": "in_review", "todo": "todo", "to do": "todo", "open": "open",
    "backlog": "backlog", "cancelled": "cancelled", "canceled": "cancelled",
}
_ST = "|".join(sorted(map(re.escape, _STATUS_MAP), key=len, reverse=True))
_PR = "low|medium|high|urgent"
_I = re.I


def _clarify(msg: str) -> RuleDraft:
    return RuleDraft(needs_clarification=True, clarification=msg)


def parse_rule_text(db: Session, owner_id: str, text: str, *, user_email: Optional[str] = None,
                    project_id: Optional[str] = None) -> RuleDraft:
    """
    Deterministic sentence -> structured rule. Output is only a *draft* validated by
    RuleDefinition; it is stored as an inactive rule and must be previewed before it
    can run, so untrusted text cannot become an execution path.
    """
    raw = re.sub(r"\s+", " ", text or "").strip()
    m = re.match(r"^(?:whenever|when|if|every time|each time|as soon as)\s+(?P<trig>.+?)\s*(?:,|;|\bthen\b)\s*(?P<acts>.+)$", raw, _I)
    if not m:
        return _clarify('Say it like: "whenever a high-priority task becomes overdue, notify me and create a follow-up".')
    trig_text, acts_text = m.group("trig"), m.group("acts")
    low = trig_text.lower()

    trigger: Optional[dict] = None
    if re.search(r"\b(?:becomes?|is|gets?|goes?|are)\s+(?:overdue|late|past due)\b", low):
        trigger = {"type": "overdue"}
    elif re.search(r"\b(?:is|are|gets?)\s+(?:created|added|filed|logged)\b", low):
        trigger = {"type": "item_created"}
    else:
        pm = re.search(rf"\bpriority\s+(?:changes?|is\s+(?:set|changed)|becomes|goes\s+up)\s+to\s+({_PR})\b", low)
        sm = re.search(rf"\b(?:status\s+)?(?:changes?|moves?|goes|is\s+(?:set|marked|moved|changed))\s+(?:to|as)\s+({_ST})\b", low) \
            or re.search(rf"\b(?:becomes?|is|gets?)\s+(?:marked\s+(?:as\s+)?)?({_ST})\b", low)
        if pm:
            trigger = {"type": "priority_changed", "to": pm.group(1)}
        elif sm:
            trigger = {"type": "status_changed", "to": _STATUS_MAP[sm.group(1)]}
        else:
            bp = re.search(rf"\bbecomes?\s+({_PR})\b", low)
            if bp:
                trigger = {"type": "priority_changed", "to": bp.group(1)}
    if trigger is None:
        return _clarify("I couldn't tell what should trigger this. Try: becomes overdue / is created / "
                        "status changes to <status> / priority changes to <priority>.")

    cond: dict[str, Any] = {"priority": [], "status": [], "type": [], "unassigned": False}
    pmatch = re.search(rf"\b({_PR})[- ]priority\b", low) or re.search(r"\b(urgent|critical)\s+(?:task|item|bug|issue|ticket)", low)
    if pmatch and trigger.get("type") != "priority_changed":
        cond["priority"] = ["urgent" if pmatch.group(1) == "critical" else pmatch.group(1)]
    if re.search(r"\bbugs?\b", low):
        cond["type"] = ["BUG"]
    elif re.search(r"\bfeatures?\b", low):
        cond["type"] = ["FEATURE"]
    if re.search(r"\bunassigned\b", low):
        cond["unassigned"] = True

    proj_id = project_id
    pj = re.search(r"\bin\s+(?:the\s+)?(?:project\s+)?[\"“']?(?P<n>\w[\w .-]{0,60}?)[\"”']?(?:\s+project)?\s*$", trig_text, _I)
    if pj and not proj_id:
        name = pj.group("n").strip()
        hits = [p for p in workgraph_service.list_projects(db, owner_id) if p.name.strip().lower() == name.lower()]
        if len(hits) == 1:
            proj_id = hits[0].id
        elif len(hits) > 1:
            return _clarify(f"You have several projects named '{name}'. Which one?")
        # no match => the words after "in" were not a project name; ignore quietly

    actions: list[dict] = []
    for part in [p.strip() for p in re.split(r"\s*(?:,|;|\band then\b|\bthen\b|\band\b)\s*", acts_text) if p.strip(" .")]:
        pl = part.lower().strip(" .")
        a = None
        if re.search(r"\b(?:notify|alert|remind|let me know|send me a notification|ping)\b", pl):
            mm = re.search(r"\bthat\s+(.+)$", part, _I)
            a = {"type": "notify", "value": mm.group(1).strip()[:255] if mm else None}
        elif re.search(r"\bfollow[- ]?up\b", pl):
            mm = re.search(r"(?:titled|called|named)\s+[\"“']?(.+?)[\"”']?$", part, _I)
            a = {"type": "create_followup", "value": mm.group(1).strip()[:255] if mm else None}
        elif (mm := re.search(r"\bassign(?:\s+it)?\s+to\s+(\S+)", pl)):
            who = mm.group(1).strip(".,;")
            if who == "me":
                if not user_email:
                    return _clarify("I don't know who 'me' is, so I can't assign to you.")
                who = user_email
            a = {"type": "assign", "value": who}
        elif (mm := re.search(rf"\b(?:set|make|change|mark|escalate)\b.*?\b({_PR})\b", pl)) and "status" not in pl:
            a = {"type": "set_priority", "value": mm.group(1)}
        elif re.search(r"\bescalate\b", pl):
            a = {"type": "set_priority", "value": "urgent"}
        elif (mm := re.search(rf"\b(?:set|mark|move|change)\b.*?\b(?:to|as)\s+({_ST})\b", pl)):
            a = {"type": "set_status", "value": _STATUS_MAP[mm.group(1)]}
        if a is None:
            return _clarify(f"I didn't understand this action: '{part}'. Supported: notify me, create a follow-up, "
                            "set priority to <p>, set status to <s>, assign to <person>.")
        actions.append(a)

    try:
        defn = RuleDefinition(name=raw[:80], project_id=proj_id, trigger=trigger, conditions=cond, actions=actions)
    except ValidationError as exc:
        return _clarify("That rule wasn't valid: " + "; ".join(e["msg"] for e in exc.errors())[:300])
    return RuleDraft(definition=defn, warnings=["Not active yet: preview it, then activate it."])
