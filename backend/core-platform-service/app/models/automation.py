"""
Automation model (AMOF-X Phase 8): scheduled/conditional workflows that
resolve to a real SupervisorPlan template, dispatched through
AMOFSupervisor.run(preset_plan=...) -- the exact same approval-gated path
an interactive request uses (see supervisor.py's `run()` docstring). No
second plan format: `task_graph_template` is a JSON-serialized
SupervisorPlan-shaped dict (a "steps" list of PlanStep-shaped objects).
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, Boolean, Index
from app.db.database import Base


class Automation(Base):
    __tablename__ = "automations"

    id = Column(String(64), primary_key=True, default=lambda: f"auto_{uuid.uuid4().hex[:10]}")
    owner_id = Column(String(64), nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # "schedule" | "condition" | "event"
    trigger_type = Column(String(16), nullable=False)
    # Cron string, e.g. "0 9 * * 1" -- only meaningful for trigger_type="schedule".
    schedule = Column(String(128), nullable=True)
    # JSON, e.g. {"event_type": "task_completed"} -- only meaningful for
    # trigger_type in ("condition", "event"); matched against real Event rows
    # published on the Redis Stream (app/events/publisher.py).
    condition = Column(Text, nullable=True)

    # JSON-serialized SupervisorPlan-shaped template: {"steps": [...]}.
    task_graph_template = Column(Text, nullable=False)

    enabled = Column(Boolean, nullable=False, default=True)
    # JSON array, append-only: [{"run_at": ..., "status": ..., "request_id": ...}, ...]
    execution_history = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        Index("ix_automations_owner_enabled", "owner_id", "enabled"),
    )
