"""
WorkGraph models (AMOF-X Phase 6): Project/Task/TaskDependency.

Deliberately scoped small -- not a Jira clone. Just enough that CDRP
(Phase 4), Meeting (Phase 7), and Automation (Phase 8) output has somewhere
real to put "unresolved issue," with AI-created and human-created work
indistinguishable in the schema except for created_by/source_type (this
phase's own acceptance criterion: same table, same constraints, no parallel
"AI tasks" system).

Tenant-scoped the same way Execution/WorkflowPlan already are (owner_id, an
opaque tenant string, indexed and filtered in every service query) rather
than Approval's heavier user_id+workspace_id scheme -- WorkGraph tasks don't
need Approval's strict-int-FK-plus-derived-workspace machinery, so adding it
would be a second isolation convention for no real requirement.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from app.db.database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(String(64), primary_key=True, default=lambda: f"proj_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="active", index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    tasks = relationship("Task", back_populates="project")

    __table_args__ = (
        Index("ix_projects_owner_created", "owner_id", "created_at"),
    )


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(64), primary_key=True, default=lambda: f"task_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)
    project_id = Column(String(64), ForeignKey("projects.id"), nullable=True, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    assignee = Column(String(255), nullable=True)
    priority = Column(String(32), nullable=False, default="medium")
    status = Column(String(32), nullable=False, default="open", index=True)
    due_date = Column(DateTime, nullable=True)

    # "human" | "ai" -- the only field that distinguishes an AI-created task
    # from a human-created one; everything else about the row is identical.
    created_by = Column(String(16), nullable=False, default="human")
    # "user_request" | "meeting_action_item" | "cdrp_replan" | "manual"
    source_type = Column(String(32), nullable=False, default="manual")
    # Traces source_type back to what actually produced this row (a
    # workflow_step_id, a meeting_id, ...) so it's checkable, not just a label.
    source_ref = Column(String(64), nullable=True)

    # AMOF Work (PRD v3 §8): "TASK" | "BUG" | "FEATURE".
    type = Column(String(16), nullable=False, default="TASK", server_default="TASK")
    # Who actually produced this row: "user:<id>" or "agent:<name>". Finer-grained
    # than created_by ("human"|"ai"); PRD "source" == source_type above.
    created_by_actor = Column(String(96), nullable=True)
    # 0..1, set only for AI-created/modified items.
    ai_confidence = Column(Float, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    project = relationship("Project", back_populates="tasks")

    __table_args__ = (
        Index("ix_tasks_owner_status", "owner_id", "status"),
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False, index=True)
    depends_on_task_id = Column(String(64), ForeignKey("tasks.id"), nullable=False, index=True)
    # Canonical storage is "task_id <kind> depends_on_task_id". "BLOCKS" requests
    # are normalised by the service into a BLOCKED_BY row on the other task.
    # Only BLOCKED_BY edges participate in cycle checks / blocker analysis.
    kind = Column(String(16), nullable=False, default="BLOCKED_BY", server_default="BLOCKED_BY")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    task = relationship("Task", foreign_keys=[task_id])
    depends_on_task = relationship("Task", foreign_keys=[depends_on_task_id])

    __table_args__ = (
        Index("ix_task_deps_unique", "task_id", "depends_on_task_id", unique=True),
    )


class WorkItemActivity(Base):
    """
    Append-only event trail per work item. There is deliberately no update or
    delete path anywhere in the service/API; the AI layer reads this to reason
    about state.

    Tenancy note: AMOF Work uses owner_id (the authenticated user) as its
    effective tenant boundary. This is per-user isolation, NOT multi-tenant
    organizations or RBAC.
    """
    __tablename__ = "work_item_activity"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String(64), nullable=False, index=True)
    # Deliberately NOT a ForeignKey: the trail is an audit log that must be able
    # to outlive its task, and a hard FK breaks any task hard-delete (tests, admin cleanup).
    task_id = Column(String(64), nullable=False, index=True)
    actor = Column(String(96), nullable=False)
    event_type = Column(String(48), nullable=False)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_activity_owner_task_created", "owner_id", "task_id", "created_at"),
    )


class WorkItemComment(Base):
    """
    Comments on a work item (PRD v3 section 7.2). Single-owner tenancy: only the owning
    user can read/write them; `author` is always server-derived, never client input.
    Comment text is untrusted DATA everywhere: it is stored and returned verbatim,
    never interpreted, and any AI use of it must go through the trust-boundary wrapper.
    """
    __tablename__ = "work_item_comments"

    id = Column(String(64), primary_key=True, default=lambda: f"cmt_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)
    # No FK, like work_item_activity: the discussion record must not block task cleanup.
    task_id = Column(String(64), nullable=False, index=True)
    author = Column(String(96), nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_comments_owner_task_created", "owner_id", "task_id", "created_at"),)
