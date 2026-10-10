"""
AI Work Command (PRD v3 §6.2 #1): natural-language read commands run immediately;
every mutating command becomes a proposal first -- no exceptions.

The interpreter is deliberately deterministic (anchored patterns, no LLM): the
decision "does this mutate?" is made by code, never by a model, so text can't
talk its way from a read into a write. A command yields at most ONE proposal;
bulk requests and anything unrecognised are refused rather than guessed at.

This module has no WorkGraph write path of its own: reads go through
workgraph_service / the read-only agents, writes only through
orchestrator.capture() / pipeline.create_proposal().
"""
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.work_agents import similarity
from app.services.work_ai import orchestrator, pipeline
from app.services.workgraph_service import workgraph_service

_STATUS_WORDS = {
    "done": "done", "complete": "done", "completed": "done", "finished": "done",
    "in progress": "in_progress", "started": "in_progress", "doing": "in_progress",
    "in review": "in_review", "blocked": "blocked",
    "todo": "open", "to do": "open", "open": "open", "reopened": "open",
    "backlog": "backlog", "cancelled": "cancelled", "canceled": "cancelled",
}
_STATUS_ALT = "|".join(sorted(map(re.escape, _STATUS_WORDS), key=len, reverse=True))
_TASK_ID = re.compile(r"\btask_[0-9a-f]{10}\b")
_READ_START = re.compile(r"^(?:what|which|who|how|when|where|show|list|find|search|get|give|tell)\b", re.I)
_BULK = re.compile(r"\b(?:all|every|each)\b", re.I)
_LIMIT = 25

_P = re.I
_NOUN = r"(?:task|bug|feature|item|ticket|issue)"
# Unambiguous create forms only: "open tasks" / "new tasks this week" are *lists*, not creates.
_CREATE = re.compile(rf"^(?:please\s+)?(?:(?:create|add)\s+(?:a\s+|an\s+|the\s+)?(?:new\s+)?(?:(?P<n1>{_NOUN})\b)?"
                     rf"|(?:new|file|log)\s+(?:a\s+|an\s+)?(?P<n2>{_NOUN})\b)\s*[:\-]?\s*(?P<rest>.+)$", _P)
_SET_STATUS = re.compile(rf"^(?:mark|set|move|change|update)\s+(?P<t>.+?)\s+(?:as|to)\s+(?P<s>{_STATUS_ALT})$", _P)
_VERB_STATUS = re.compile(r"^(?P<v>complete|finish|close|reopen|start)\s+(?P<t>.+)$", _P)
_SET_PRIORITY = re.compile(r"^(?:set|change|update)\s+(?:the\s+)?priority\s+(?:of\s+)?(?P<t>.+?)\s+(?:to|as)\s+"
                           r"(?P<p>low|medium|high|urgent)$", _P)
_MAKE_PRIORITY = re.compile(r"^(?:make|mark)\s+(?P<t>.+?)\s+(?P<p>low|medium|high|urgent)(?:\s+priority)?$", _P)
_ASSIGN = re.compile(r"^assign\s+(?P<t>.+?)\s+to\s+(?P<w>\S+)$", _P)
_LINK = [
    (re.compile(r"^(?P<a>.+?)\s+(?:is\s+)?blocked\s+by\s+(?P<b>.+)$", _P), "BLOCKED_BY"),
    (re.compile(r"^(?P<a>.+?)\s+blocks\s+(?P<b>.+)$", _P), "BLOCKS"),
    (re.compile(r"^(?P<a>.+?)\s+(?:is\s+)?relate[sd]?\s+to\s+(?P<b>.+)$", _P), "RELATES_TO"),
]
_WHATS_BLOCKING = re.compile(r"^what(?:'s|\s+is|\s+are)?\s+(?:currently\s+)?(?:blocking\s*(?P<t>.*?)|blocked)\s*\??$", _P)

HELP = ("I can answer questions (e.g. \"what's blocking <item>?\", \"show me overdue work\", \"what should I focus on today?\", "
        "\"any risks?\") and queue changes for your approval (e.g. \"create a bug: login fails\", \"mark <item> as done\", "
        "\"set priority of <item> to high\", \"assign <item> to <person>\", \"<item> is blocked by <item>\").")


def _resp(mode: str, answer: str, data: Optional[dict] = None, proposals: Optional[list] = None) -> dict[str, Any]:
    return {"mode": mode, "answer": answer, "data": data or {}, "proposals": proposals or []}


def _item(t) -> dict[str, Any]:
    return {"id": t.id, "title": t.title, "status": t.status, "priority": t.priority,
            "due_date": t.due_date.isoformat() if t.due_date else None, "assignee": t.assignee}


def _clean_target(phrase: str) -> str:
    p = phrase.strip().strip("\"'`").strip()
    return re.sub(r"^(?:the|my|task|item|ticket|issue)\s+", "", p, flags=re.I).strip("\"'`? .")


def _resolve(db: Session, owner_id: str, phrase: str, project_id: Optional[str]):
    """-> (task, None) | (None, candidates). Never guesses between several plausible items."""
    phrase = _clean_target(phrase)
    if not phrase:
        return None, []
    m = _TASK_ID.search(phrase)
    if m:
        t = workgraph_service.get_task(db, owner_id, m.group(0))
        return (t, None) if t else (None, [])
    pool = [t for t in workgraph_service.list_tasks(db, owner_id, project_id=project_id) if t.status != "cancelled"]
    exact = [t for t in pool if t.title.strip().lower() == phrase.lower()]
    if len(exact) == 1:
        return exact[0], None
    contains = [t for t in pool if phrase.lower() in t.title.lower()]
    if len(contains) == 1:
        return contains[0], None
    cands = exact or contains
    if not cands:
        scored = sorted(((similarity(phrase, t.title), t) for t in pool), key=lambda x: -x[0])
        cands = [t for s, t in scored if s >= 0.75][:5]
        if len(cands) == 1:
            return cands[0], None
    return None, cands[:5]


def _need_one(db, owner_id, phrase, project_id):
    task, cands = _resolve(db, owner_id, phrase, project_id)
    if task is not None:
        return task, None
    if cands:
        return None, _resp("clarify", f"'{phrase}' matches several items -- which one did you mean?",
                           {"candidates": [_item(c) for c in cands]})
    return None, _resp("clarify", f"I couldn't find an item matching '{phrase}'. Nothing was changed.")


def _queue(db, owner_id, *, kind, payload, explanation, confidence=0.9) -> dict[str, Any]:
    prop = pipeline.create_proposal(db, owner_id, kind=kind, payload=payload, agent="command", source="user_command",
                                    confidence=confidence, explanation=explanation)
    if prop.status == "EXECUTED":
        return _resp("proposal", f"Done -- applied automatically under your L3 grant: {explanation}", proposals=[prop])
    return _resp("proposal", f"Queued in your AI Inbox for approval (nothing has changed yet): {explanation}", proposals=[prop])


# =========================================================================== mutating

def _mutating(db, owner_id, text, project_id, user_email) -> Optional[dict[str, Any]]:
    m = _SET_STATUS.search(text) or _VERB_STATUS.search(text)
    if m:
        if _BULK.search(text):
            return _resp("unsupported", "Bulk changes aren't supported yet -- name a single item.")
        if "s" in m.groupdict() and m.group("s"):
            status = _STATUS_WORDS[m.group("s").lower()]
        else:
            status = {"complete": "done", "finish": "done", "close": "done", "reopen": "open", "start": "in_progress"}[m.group("v").lower()]
        task, clarify = _need_one(db, owner_id, m.group("t"), project_id)
        if clarify:
            return clarify
        if task.status == status:
            return _resp("read", f"'{task.title}' is already {status.replace('_', ' ')}. No change needed.", {"item": _item(task)})
        return _queue(db, owner_id, kind="update_item", payload={"task_id": task.id, "status": status},
                      explanation=f"change '{task.title}' from {task.status.replace('_', ' ')} to {status.replace('_', ' ')}")

    m = _SET_PRIORITY.search(text) or _MAKE_PRIORITY.search(text)
    if m:
        if _BULK.search(text):
            return _resp("unsupported", "Bulk changes aren't supported yet -- name a single item.")
        task, clarify = _need_one(db, owner_id, m.group("t"), project_id)
        if clarify:
            return clarify
        pr = m.group("p").lower()
        if task.priority == pr:
            return _resp("read", f"'{task.title}' already has {pr} priority. No change needed.", {"item": _item(task)})
        return _queue(db, owner_id, kind="update_item", payload={"task_id": task.id, "priority": pr},
                      explanation=f"set priority of '{task.title}' to {pr}")

    m = _ASSIGN.search(text)
    if m:
        if _BULK.search(text):
            return _resp("unsupported", "Bulk changes aren't supported yet -- name a single item.")
        task, clarify = _need_one(db, owner_id, m.group("t"), project_id)
        if clarify:
            return clarify
        who = m.group("w").strip(".,;")
        if who.lower() == "me":
            if not user_email:
                return _resp("clarify", "I don't know who 'me' is here. Nothing was changed.")
            who = user_email
        return _queue(db, owner_id, kind="update_item", payload={"task_id": task.id, "assignee": who},
                      explanation=f"assign '{task.title}' to {who}")

    for rx, link_kind in _LINK:
        m = rx.search(text)
        if m:
            a, ca = _need_one(db, owner_id, m.group("a"), project_id)
            if ca:
                return ca
            b, cb = _need_one(db, owner_id, m.group("b"), project_id)
            if cb:
                return cb
            if a.id == b.id:
                return _resp("clarify", "Those are the same item. Nothing was changed.")
            verb = {"BLOCKED_BY": "is blocked by", "BLOCKS": "blocks", "RELATES_TO": "relates to"}[link_kind]
            return _queue(db, owner_id, kind="link_items",
                          payload={"task_id": a.id, "other_task_id": b.id, "link_kind": link_kind},
                          explanation=f"link: '{a.title}' {verb} '{b.title}'")

    m = _CREATE.search(text)
    if m:
        noun, rest = (m.group("n1") or m.group("n2") or "").lower(), m.group("rest").strip()
        if not rest:
            return _resp("clarify", "What should the new item say?")
        out = orchestrator.capture(db, owner_id, rest, source="user_command", project_id=project_id, user_email=user_email,
                                   type_hint={"bug": "BUG", "feature": "FEATURE"}.get(noun))
        prop, warn = out["proposal"], out["duplicate_warning"]
        props = [prop] + ([warn] if warn else [])
        note = " A possible duplicate was flagged in your inbox." if warn else ""
        if prop.status == "EXECUTED":
            return _resp("proposal", f"Done -- created '{prop.payload['title']}' automatically under your L3 grant.{note}", proposals=props)
        return _resp("proposal", f"Queued in your AI Inbox for approval (nothing has changed yet): create '{prop.payload['title']}'.{note}",
                     {"draft": out["draft"].model_dump()}, props)
    return None


# =========================================================================== read-only

def _read(db, owner_id, text, project_id, user_email) -> Optional[dict[str, Any]]:
    m = _WHATS_BLOCKING.search(text)
    if m:
        target = m.group("t") or ""
        if not _clean_target(target):
            rep = orchestrator.risks(db, owner_id, project_id=project_id)
            chains = [r.model_dump() for r in rep.risks if r.type == "blocked_chain"]
            return _resp("read", f"{len(chains)} item(s) are blocked by unfinished work." if chains else "Nothing is blocked right now.",
                         {"blocked": chains})
        task, clarify = _need_one(db, owner_id, target, project_id)
        if clarify:
            return clarify
        ids = workgraph_service.get_links(db, owner_id, task.id)["blocked_by"]
        blockers = [b for b in (workgraph_service.get_task(db, owner_id, i) for i in ids) if b and b.status not in ("done", "cancelled")]
        if not blockers:
            return _resp("read", f"Nothing is blocking '{task.title}'.", {"item": _item(task), "blockers": []})
        return _resp("read", f"'{task.title}' is blocked by: " + ", ".join(f"{b.title} ({b.status.replace('_', ' ')})" for b in blockers),
                     {"item": _item(task), "blockers": [_item(b) for b in blockers]})

    low = text.lower()
    if re.search(r"\b(?:overdue|past due|late)\b", low):
        items = workgraph_service.list_tasks(db, owner_id, project_id=project_id, overdue=True)[:_LIMIT]
        return _resp("read", f"{len(items)} overdue item(s)." if items else "Nothing is overdue.", {"items": [_item(t) for t in items]})
    if re.search(r"\bfocus\b|work on today|what should i (?:do|work)|plan my day|priorit(?:y|ies) today", low):
        plan = orchestrator.focus_plan(db, owner_id, project_id=project_id, user_email=user_email)
        return _resp("read", plan.summary, plan.model_dump())
    if re.search(r"\brisks?\b|\bat risk\b", low):
        rep = orchestrator.risks(db, owner_id, project_id=project_id)
        return _resp("read", f"{len(rep.risks)} risk(s) found." if rep.risks else "No risks found.", rep.model_dump())
    if re.search(r"\bhow many\b|\bcount\b|\boverview\b|\bsummary\b", low):
        counts = workgraph_service.dashboard(db, owner_id)["counts"]
        return _resp("read", ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in counts.items()), {"counts": counts})

    m = re.match(r"^(?:show|list|find|search|get|give)(?:\s+me)?(?:\s+all)?(?:\s+my)?(?:\s+for)?\s+(?P<q>.+)$", text, _P)
    if m:
        q, status, priority, typ, unassigned = m.group("q").lower(), None, None, None, False
        for word in sorted(_STATUS_WORDS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(word)}\b", q):
                status = _STATUS_WORDS[word]
                q = re.sub(rf"\b{re.escape(word)}\b", " ", q)
                break
        pm = re.search(r"\b(low|medium|high|urgent)\b", q)
        if pm:
            priority, q = pm.group(1), q.replace(pm.group(0), " ")
        if re.search(r"\bbugs?\b", q):
            typ = "BUG"
        elif re.search(r"\bfeatures?\b", q):
            typ = "FEATURE"
        if re.search(r"\bunassigned\b", q):
            unassigned = True
        q = re.sub(r"\b(?:tasks?|items?|work|tickets?|issues?|bugs?|features?|priority|unassigned|that are|which are|are|is|the)\b", " ", q)
        term = re.sub(r"\s+", " ", q).strip(" ?.")
        items = workgraph_service.list_tasks(db, owner_id, project_id=project_id, status=status, priority=priority, type=typ,
                                             search=term or None)
        if unassigned:
            items = [t for t in items if not t.assignee]
        items = items[:_LIMIT]
        return _resp("read", f"{len(items)} item(s) found." if items else "No matching items.", {"items": [_item(t) for t in items]})
    return None


def execute(db: Session, owner_id: str, command: str, *, project_id: Optional[str] = None,
            user_email: Optional[str] = None) -> dict[str, Any]:
    text = re.sub(r"\s+", " ", command or "").strip()
    if not text:
        raise ValueError("Empty command.")
    if project_id and workgraph_service.get_project(db, owner_id, project_id) is None:
        raise ValueError("Project not found.")

    if _READ_START.match(text):  # questions/searches are read-only by construction
        out = _read(db, owner_id, text, project_id, user_email)
    else:
        out = _mutating(db, owner_id, text, project_id, user_email) or _read(db, owner_id, text, project_id, user_email)
    return out or _resp("unsupported", "I didn't understand that, so I did nothing. " + HELP)
