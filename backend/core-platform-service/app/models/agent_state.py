"""
Phase 24: Run Blackboard persistence model.

`AgentStateEntry` is the durable row behind `app.supervisor.blackboard.RunBlackboard`.
It is deliberately append-only -- a later `put()` under the same key inserts a
new row rather than updating the old one, so `history(key)` can replay exactly
what was known at each point in the run (needed for CDRP replan inspection and
later attribution/recovery phases). `owner_id` is mandatory and every read path
in `RunBlackboard` filters on it: there is no method that can return another
owner's rows, mirroring the isolation discipline in
`app/models/routing_decision.py` and `tests/security/test_owner_isolation.py`.
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, String, Text, DateTime, Index
from app.db.database import Base


class AgentStateEntry(Base):
    __tablename__ = "agent_state_entries"

    id = Column(String(64), primary_key=True, default=lambda: f"state_{uuid.uuid4().hex[:12]}")

    # The run this entry belongs to. Ties to WorkflowPlan.id/plan_id -- one
    # blackboard per orchestration run.
    run_id = Column(String(64), nullable=False, index=True)

    # Mandatory: every read is scoped by (run_id, owner_id) together, never
    # run_id alone.
    owner_id = Column(String(64), nullable=False, index=True)

    key = Column(String(255), nullable=False)
    value_json = Column(Text, nullable=False)

    # step_id of the step that produced this value, or None for a write not
    # attributed to a specific step.
    written_by_step = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_agent_state_run_key", "run_id", "key"),
    )
