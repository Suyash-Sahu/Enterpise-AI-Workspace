"""
WorkGraph service (AMOF-X Phase 6, extended for AMOF Work stage 1): CRUD over
Project/Task/TaskDependency plus the append-only WorkItemActivity trail.

Mirrors app/services/approval/approval_service.py's shape (a thin class over
direct DB queries) rather than introducing a new service-layer convention.

Tenancy: every query is scoped by owner_id, which the API derives from the
authenticated user. This is per-user isolation -- not organizations/RBAC.
Any project_id / depends_on / task id supplied by a caller is re-checked
against owner_id here; ids are never trusted.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.events import Event, EventType, event_publisher
from app.models.workgraph import Project, Task, TaskDependency, WorkItemActivity, WorkItemComment
from app.schemas.workgraph import TaskResponse

# Board / dashboard buckets over the finer-grained status vocabulary.
STATUS_BUCKETS = {
    "open": ("backlog", "open", "todo"),
    "in_progress": ("in_progress", "in_review"),
    "blocked": ("blocked",),
    "done": ("done",),
}
CLOSED_STATUSES = ("done", "cancelled")

# Fields update_task may touch. owner_id / provenance are never client-settable.
UPDATABLE_FIELDS = ("title", "description", "assignee", "priority", "status", "type", "due_date")

_MAX_LINKS_WALKED = 5000


def _now() -> datetime:
    # Columns are naive-UTC in SQLite/Postgres DateTime; compare like with like.
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _naive(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is not None and dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt


class WorkGraphService:

    # ------------------------------------------------------------------
    # Activity (append-only)
    # ------------------------------------------------------------------

    @staticmethod
    def _log(db: Session, owner_id: str, task_id: str, actor: str, event_type: str, payload: Optional[dict] = None) -> None:
        """Stage an activity row in the caller's transaction (caller commits)."""
        db.add(WorkItemActivity(
            owner_id=owner_id, task_id=task_id, actor=actor,
            event_type=event_type, payload=payload,
        ))

    @staticmethod
    def list_activity(db: Session, owner_id: str, task_id: str, limit: int = 100) -> list[WorkItemActivity]:
        if WorkGraphService.get_task(db, owner_id, task_id) is None:
            raise ValueError("Task not found.")
        return (
            db.query(WorkItemActivity)
            .filter(WorkItemActivity.owner_id == owner_id, WorkItemActivity.task_id == task_id)
            .order_by(WorkItemActivity.id.desc())
            .limit(max(1, min(limit, 500)))
            .all()
        )

    # ------------------------------------------------------------------
    # Comments (single-owner; text is stored/returned verbatim, never interpreted)
    # ------------------------------------------------------------------

    @staticmethod
    def create_comment(db: Session, owner_id: str, task_id: str, body: str) -> WorkItemComment:
        body = (body or "").strip()
        if not body or len(body) > 5000:
            raise ValueError("Comment must be 1-5000 characters.")
        if WorkGraphService.get_task(db, owner_id, task_id) is None:
            raise ValueError("Task not found.")
        now = datetime.now(timezone.utc)  # one value for both, so a fresh comment is never "edited"
        comment = WorkItemComment(owner_id=owner_id, task_id=task_id, author=f"user:{owner_id}", body=body,
                                  created_at=now, updated_at=now)
        db.add(comment)
        db.flush()
        WorkGraphService._log(db, owner_id, task_id, comment.author, "comment_added", {"comment_id": comment.id})
        db.commit()
        db.refresh(comment)
        return comment

    @staticmethod
    def list_comments(db: Session, owner_id: str, task_id: str, limit: int = 100) -> list[WorkItemComment]:
        if WorkGraphService.get_task(db, owner_id, task_id) is None:
            raise ValueError("Task not found.")
        return (
            db.query(WorkItemComment)
            .filter(WorkItemComment.owner_id == owner_id, WorkItemComment.task_id == task_id)
            .order_by(WorkItemComment.created_at, WorkItemComment.id)
            .limit(max(1, min(limit, 500)))
            .all()
        )

    @staticmethod
    def get_comment(db: Session, owner_id: str, comment_id: str) -> Optional[WorkItemComment]:
        return (
            db.query(WorkItemComment)
            .filter(WorkItemComment.id == comment_id, WorkItemComment.owner_id == owner_id)
            .first()
        )

    @staticmethod
    def update_comment(db: Session, owner_id: str, comment_id: str, body: str) -> Optional[WorkItemComment]:
        comment = WorkGraphService.get_comment(db, owner_id, comment_id)
        if comment is None:
            return None
        body = (body or "").strip()
        if not body or len(body) > 5000:
            raise ValueError("Comment must be 1-5000 characters.")
        comment.body = body
        WorkGraphService._log(db, owner_id, comment.task_id, f"user:{owner_id}", "comment_edited", {"comment_id": comment.id})
        db.commit()
        db.refresh(comment)
        return comment

    @staticmethod
    def delete_comment(db: Session, owner_id: str, comment_id: str) -> bool:
        comment = WorkGraphService.get_comment(db, owner_id, comment_id)
        if comment is None:
            return False
        WorkGraphService._log(db, owner_id, comment.task_id, f"user:{owner_id}", "comment_deleted", {"comment_id": comment.id})
        db.delete(comment)
        db.commit()
        return True

    # ------------------------------------------------------------------
    # Projects
    # ------------------------------------------------------------------

    @staticmethod
    def create_project(db: Session, owner_id: str, name: str, description: Optional[str] = None) -> Project:
        project = Project(owner_id=owner_id, name=name, description=description)
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def list_projects(db: Session, owner_id: str) -> list[Project]:
        return (
            db.query(Project)
            .filter(Project.owner_id == owner_id)
            .order_by(Project.created_at.desc())
            .all()
        )

    @staticmethod
    def get_project(db: Session, owner_id: str, project_id: str) -> Optional[Project]:
        return (
            db.query(Project)
            .filter(Project.id == project_id, Project.owner_id == owner_id)
            .first()
        )

    @staticmethod
    def update_project(db: Session, owner_id: str, project_id: str, **fields) -> Optional[Project]:
        project = WorkGraphService.get_project(db=db, owner_id=owner_id, project_id=project_id)
        if not project:
            return None
        for key in ("name", "description", "status"):
            if fields.get(key) is not None:
                setattr(project, key, fields[key])
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def _count_by_bucket(rows) -> dict[str, int]:
        counts = {b: 0 for b in STATUS_BUCKETS}
        for status, n in rows:
            for bucket, members in STATUS_BUCKETS.items():
                if status in members:
                    counts[bucket] += n
        return counts

    @staticmethod
    def project_stats(db: Session, owner_id: str, project_id: str) -> Optional[dict]:
        if WorkGraphService.get_project(db, owner_id, project_id) is None:
            return None
        rows = (
            db.query(Task.status, func.count(Task.id))
            .filter(Task.owner_id == owner_id, Task.project_id == project_id)
            .group_by(Task.status)
            .all()
        )
        overdue = db.query(func.count(Task.id)).filter(
            Task.owner_id == owner_id, Task.project_id == project_id,
            Task.due_date < _now(), Task.status.notin_(CLOSED_STATUSES),
        ).scalar() or 0
        return {
            "project_id": project_id,
            "total": sum(n for _, n in rows),
            "counts": WorkGraphService._count_by_bucket(rows),
            "overdue": overdue,
        }

    # ------------------------------------------------------------------
    # Tasks
    # ------------------------------------------------------------------

    @staticmethod
    def get_task(db: Session, owner_id: str, task_id: str) -> Optional[Task]:
        return (
            db.query(Task)
            .filter(Task.id == task_id, Task.owner_id == owner_id)
            .first()
        )

    @staticmethod
    def create_task(
        db: Session,
        owner_id: str,
        title: str,
        *,
        description: Optional[str] = None,
        project_id: Optional[str] = None,
        assignee: Optional[str] = None,
        priority: str = "medium",
        status: str = "open",
        type: str = "TASK",
        due_date: Optional[datetime] = None,
        created_by: str = "human",
        created_by_actor: Optional[str] = None,
        source_type: str = "manual",
        source_ref: Optional[str] = None,
        ai_confidence: Optional[float] = None,
        depends_on: Optional[list[str]] = None,
    ) -> Task:
        # Re-check every referenced id against the owner *before* writing.
        if project_id is not None and WorkGraphService.get_project(db, owner_id, project_id) is None:
            raise ValueError("Project not found.")
        dep_ids = list(dict.fromkeys(depends_on or []))
        for dep_id in dep_ids:
            if WorkGraphService.get_task(db, owner_id, dep_id) is None:
                raise ValueError("Dependency task not found.")

        actor = created_by_actor or (
            f"user:{owner_id}" if created_by == "human" else "agent:unknown"
        )
        task = Task(
            owner_id=owner_id,
            title=title,
            description=description,
            project_id=project_id,
            assignee=assignee,
            priority=priority,
            status=status,
            type=type,
            due_date=_naive(due_date),
            created_by=created_by,
            created_by_actor=actor,
            source_type=source_type,
            source_ref=source_ref,
            ai_confidence=ai_confidence,
        )
        db.add(task)
        db.flush()  # task.id is needed before adding dependency rows

        for dep_id in dep_ids:  # a brand-new task cannot be part of a cycle
            db.add(TaskDependency(task_id=task.id, depends_on_task_id=dep_id, kind="BLOCKED_BY"))
        WorkGraphService._log(db, owner_id, task.id, actor, "created", {
            "title": title, "source_type": source_type, "source_ref": source_ref,
            "ai_confidence": ai_confidence, "depends_on": dep_ids,
        })

        db.commit()
        db.refresh(task)

        event_publisher.publish(Event(
            event_type=EventType.TASK_CREATED,
            owner_id=owner_id,
            payload={"task_id": task.id, "title": task.title, "created_by": task.created_by, "source_type": task.source_type},
        ))

        return task

    @staticmethod
    def list_tasks(
        db: Session,
        owner_id: str,
        *,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        assignee: Optional[str] = None,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
        priority: Optional[str] = None,
        type: Optional[str] = None,
        due_before: Optional[datetime] = None,
        due_after: Optional[datetime] = None,
        overdue: bool = False,
    ) -> list[Task]:
        query = db.query(Task).filter(Task.owner_id == owner_id)
        if project_id:
            query = query.filter(Task.project_id == project_id)
        if status:
            query = query.filter(Task.status == status)
        if assignee:
            query = query.filter(Task.assignee == assignee)
        if priority:
            query = query.filter(Task.priority == priority)
        if type:
            query = query.filter(Task.type == type)
        if source_type:
            query = query.filter(Task.source_type == source_type)
        if due_before:
            query = query.filter(Task.due_date <= _naive(due_before))
        if due_after:
            query = query.filter(Task.due_date >= _naive(due_after))
        if overdue:
            query = query.filter(Task.due_date < _now(), Task.status.notin_(CLOSED_STATUSES))
        if search and search.strip():
            escaped = search.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            term = f"%{escaped}%"
            query = query.filter(or_(
                Task.title.ilike(term, escape="\\"),
                Task.description.ilike(term, escape="\\"),
            ))
        return query.order_by(Task.created_at.desc()).all()

    @staticmethod
    def update_task(
        db: Session,
        owner_id: str,
        task_id: str,
        *,
        actor: Optional[str] = None,
        ai_confidence: Optional[float] = None,
        source_ref: Optional[str] = None,
        **fields,
    ) -> Optional[Task]:
        task = WorkGraphService.get_task(db, owner_id, task_id)
        if not task:
            return None
        was_done = task.status == "done"
        actor = actor or f"user:{owner_id}"

        changes: dict[str, dict] = {}
        for key in UPDATABLE_FIELDS:
            value = fields.get(key)
            if value is None:
                continue
            if key == "due_date":
                value = _naive(value)
            old = getattr(task, key)
            if old != value:
                changes[key] = {"from": str(old) if old is not None else None, "to": str(value)}
                setattr(task, key, value)
        if ai_confidence is not None:
            task.ai_confidence = ai_confidence

        if changes:
            event = "status_changed" if set(changes) == {"status"} else "updated"
            payload = {"changes": changes}
            if source_ref:
                payload["source_ref"] = source_ref  # e.g. the AI proposal that caused this
                payload["ai_confidence"] = ai_confidence
            WorkGraphService._log(db, owner_id, task.id, actor, event, payload)
        db.commit()
        db.refresh(task)

        if task.status == "done" and not was_done:
            event_publisher.publish(Event(
                event_type=EventType.TASK_COMPLETED,
                owner_id=owner_id,
                payload={"task_id": task.id, "title": task.title},
            ))

        return task

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    @staticmethod
    def _reaches(db: Session, owner_id: str, start_id: str, target_id: str) -> bool:
        """True if `start_id` is (transitively) BLOCKED_BY `target_id`."""
        seen, frontier = {start_id}, [start_id]
        while frontier and len(seen) < _MAX_LINKS_WALKED:
            rows = (
                db.query(TaskDependency.depends_on_task_id)
                .join(Task, Task.id == TaskDependency.task_id)
                .filter(
                    Task.owner_id == owner_id,
                    TaskDependency.kind == "BLOCKED_BY",
                    TaskDependency.task_id.in_(frontier),
                )
                .all()
            )
            frontier = []
            for (nxt,) in rows:
                if nxt == target_id:
                    return True
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
        return False

    @staticmethod
    def add_dependency(
        db: Session,
        owner_id: str,
        task_id: str,
        depends_on_task_id: str,
        kind: str = "BLOCKED_BY",
        actor: Optional[str] = None,
        source_ref: Optional[str] = None,
    ) -> TaskDependency:
        if task_id == depends_on_task_id:
            raise ValueError("A task cannot depend on itself.")
        if kind not in ("BLOCKS", "BLOCKED_BY", "RELATES_TO"):
            raise ValueError("Invalid dependency kind.")

        # Both ends must belong to the current owner (unauthorised-link guard).
        if WorkGraphService.get_task(db, owner_id, task_id) is None:
            raise ValueError("Task not found.")
        if WorkGraphService.get_task(db, owner_id, depends_on_task_id) is None:
            raise ValueError("Dependency task not found.")

        # Normalise "A BLOCKS B" to the canonical row "B BLOCKED_BY A".
        if kind == "BLOCKS":
            task_id, depends_on_task_id, kind = depends_on_task_id, task_id, "BLOCKED_BY"

        existing = (
            db.query(TaskDependency)
            .filter(TaskDependency.task_id == task_id, TaskDependency.depends_on_task_id == depends_on_task_id)
            .first()
        )
        if existing:
            if existing.kind != kind:
                raise ValueError(f"A {existing.kind} link already exists between these tasks.")
            return existing

        # `task_id` blocked by `depends_on` is circular iff `depends_on` is
        # already (transitively) blocked by `task_id`.
        if kind == "BLOCKED_BY" and WorkGraphService._reaches(db, owner_id, depends_on_task_id, task_id):
            raise ValueError("Circular dependency rejected.")

        dependency = TaskDependency(task_id=task_id, depends_on_task_id=depends_on_task_id, kind=kind)
        db.add(dependency)
        WorkGraphService._log(db, owner_id, task_id, actor or f"user:{owner_id}", "dependency_added",
                              {"other": depends_on_task_id, "kind": kind, "source_ref": source_ref})
        db.commit()
        db.refresh(dependency)
        return dependency

    @staticmethod
    def remove_dependency(
        db: Session,
        owner_id: str,
        task_id: str,
        depends_on_task_id: str,
        actor: Optional[str] = None,
    ) -> bool:
        if WorkGraphService.get_task(db, owner_id, task_id) is None:
            raise ValueError("Task not found.")
        if WorkGraphService.get_task(db, owner_id, depends_on_task_id) is None:
            raise ValueError("Dependency task not found.")

        dependency = (
            db.query(TaskDependency)
            .filter(TaskDependency.task_id == task_id, TaskDependency.depends_on_task_id == depends_on_task_id)
            .first()
        )
        if dependency is None:
            return False
        WorkGraphService._log(db, owner_id, task_id, actor or f"user:{owner_id}", "dependency_removed",
                              {"other": depends_on_task_id, "kind": dependency.kind})
        db.delete(dependency)
        db.commit()
        return True

    @staticmethod
    def list_dependencies(db: Session, owner_id: str, task_id: str) -> list[TaskDependency]:
        if WorkGraphService.get_task(db, owner_id, task_id) is None:
            raise ValueError("Task not found.")
        return (
            db.query(TaskDependency)
            .join(Task, Task.id == TaskDependency.depends_on_task_id)
            .filter(TaskDependency.task_id == task_id, Task.owner_id == owner_id)
            .all()
        )

    @staticmethod
    def get_links(db: Session, owner_id: str, task_id: str) -> dict[str, list[str]]:
        """Directional view of a task's links: blocked_by / blocks / relates_to."""
        if WorkGraphService.get_task(db, owner_id, task_id) is None:
            raise ValueError("Task not found.")
        out: dict[str, list[str]] = {"blocked_by": [], "blocks": [], "relates_to": []}
        rows = (
            db.query(TaskDependency)
            .join(Task, Task.id == TaskDependency.task_id)
            .filter(
                Task.owner_id == owner_id,
                or_(TaskDependency.task_id == task_id, TaskDependency.depends_on_task_id == task_id),
            )
            .all()
        )
        for r in rows:
            other = r.depends_on_task_id if r.task_id == task_id else r.task_id
            if r.kind == "RELATES_TO":
                out["relates_to"].append(other)
            elif r.task_id == task_id:
                out["blocked_by"].append(other)
            else:
                out["blocks"].append(other)
        return out

    @staticmethod
    def get_dependencies(db: Session, task_id: str) -> list[str]:
        """BLOCKED_BY ids only (the `depends_on` field). Caller must have owner-checked task_id."""
        rows = (
            db.query(TaskDependency)
            .filter(TaskDependency.task_id == task_id, TaskDependency.kind == "BLOCKED_BY")
            .all()
        )
        return [r.depends_on_task_id for r in rows]

    # ------------------------------------------------------------------
    # Dashboard / board
    # ------------------------------------------------------------------

    @staticmethod
    def dashboard(db: Session, owner_id: str) -> dict:
        rows = (
            db.query(Task.status, func.count(Task.id))
            .filter(Task.owner_id == owner_id)
            .group_by(Task.status)
            .all()
        )
        now = _now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        open_q = db.query(Task).filter(Task.owner_id == owner_id, Task.status.notin_(CLOSED_STATUSES))
        return {
            "counts": WorkGraphService._count_by_bucket(rows),
            "due_today": open_q.filter(Task.due_date >= day_start, Task.due_date < day_start + timedelta(days=1))
                               .order_by(Task.due_date).limit(50).all(),
            "overdue": open_q.filter(Task.due_date < now).order_by(Task.due_date).limit(50).all(),
            "recently_updated": db.query(Task).filter(Task.owner_id == owner_id)
                                  .order_by(Task.updated_at.desc()).limit(10).all(),
        }

    @staticmethod
    def board(db: Session, owner_id: str, project_id: str) -> Optional[dict[str, list[Task]]]:
        if WorkGraphService.get_project(db, owner_id, project_id) is None:
            return None
        tasks = WorkGraphService.list_tasks(db, owner_id, project_id=project_id)
        columns: dict[str, list[Task]] = {b: [] for b in STATUS_BUCKETS}
        for t in tasks:
            for bucket, members in STATUS_BUCKETS.items():
                if t.status in members:
                    columns[bucket].append(t)
        return columns

    # ------------------------------------------------------------------

    @staticmethod
    def to_response_dto(db: Session, task: Task) -> TaskResponse:
        # ponytail: one dependency query per task (N+1); batch if lists get large.
        return TaskResponse(
            id=task.id,
            owner_id=task.owner_id,
            project_id=task.project_id,
            title=task.title,
            description=task.description,
            assignee=task.assignee,
            priority=task.priority,
            status=task.status,
            type=task.type or "TASK",
            due_date=task.due_date,
            created_by=task.created_by,
            created_by_actor=task.created_by_actor,
            source_type=task.source_type,
            source_ref=task.source_ref,
            ai_confidence=task.ai_confidence,
            depends_on=WorkGraphService.get_dependencies(db, task.id),
            created_at=task.created_at,
            updated_at=task.updated_at,
        )


workgraph_service = WorkGraphService()
