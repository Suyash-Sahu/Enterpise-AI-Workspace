"""
Persisted task-graph models (AMOF-X Phase 1).

`SupervisorPlan`/`PlanStep` (app/schemas/supervisor.py) already model a real
DAG shape -- step_id, depends_on, status, execution_id, result. They are
Pydantic objects that live for the duration of one request and vanish on
restart. WorkflowPlan/WorkflowStep mirror that exact shape in the database so
a plan survives a process restart, and so Phase 2 (ATGO) has something to
decompose into, Phase 4 (CDRP) has something to record replanning events
against, and Phase 8 (automation) has something to check in on.

Deliberately NOT a new graph representation: field names match PlanStep's
so the mapping between the in-memory schema and the persisted row is a
straight copy, not a translation layer to maintain.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.db.database import Base


class WorkflowPlan(Base):
    __tablename__ = "workflow_plans"

    id = Column(String(64), primary_key=True, default=lambda: f"plan_{uuid.uuid4().hex[:10]}")
    request_id = Column(String(64), nullable=False, index=True)
    owner_id = Column(String(64), nullable=False, index=True)
    max_steps = Column(Integer, nullable=False, default=5)
    # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED -- mirrors PlanStep's
    # status vocabulary rather than inventing a second one.
    status = Column(String(32), nullable=False, default="PENDING", index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    steps = relationship(
        "WorkflowStep", back_populates="plan",
        order_by="WorkflowStep.created_at", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_workflow_plans_owner_created", "owner_id", "created_at"),
    )


class WorkflowStep(Base):
    __tablename__ = "workflow_steps"

    id = Column(String(64), primary_key=True, default=lambda: f"wstep_{uuid.uuid4().hex[:12]}")
    plan_id = Column(String(64), ForeignKey("workflow_plans.id"), nullable=False, index=True)

    # Matches PlanStep.step_id -- the in-graph identifier ("step_1"), not
    # this row's own primary key, so depends_on references stay stable
    # across the Pydantic<->DB boundary.
    step_id = Column(String(32), nullable=False)
    capability = Column(String(64), nullable=False, index=True)
    # JSON-encoded list[str] of prerequisite step_ids. Not a join table:
    # depends_on is small (single-digit fan-in in practice) and is read as a
    # whole with the step, never queried independently.
    depends_on_json = Column(Text, nullable=False, default="[]")
    status = Column(String(32), nullable=False, default="PENDING", index=True)
    blocked_by_step_id = Column(String(32), nullable=True)

    execution_id = Column(String(64), ForeignKey("executions.id"), nullable=True)
    replanning_of = Column(String(64), ForeignKey("workflow_steps.id"), nullable=True)
    result_json = Column(Text, nullable=True)
    verification_json = Column(Text, nullable=True)  # Phase 29: persisted VerificationReport
    execution_time = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    plan = relationship("WorkflowPlan", back_populates="steps")

    __table_args__ = (
        Index("ix_workflow_steps_plan_step", "plan_id", "step_id", unique=True),
    )


class ReplanningEvent(Base):
    __tablename__ = "replanning_events"

    id = Column(String(64), primary_key=True, default=lambda: f"replan_{uuid.uuid4().hex[:12]}")
    original_step_id = Column(String(64), ForeignKey("workflow_steps.id"), nullable=False, index=True)
    new_step_id = Column(String(64), ForeignKey("workflow_steps.id"), nullable=True, index=True)

    reason = Column(Text, nullable=False)
    confidence_before = Column(Float, nullable=False, default=0.0)
    confidence_after = Column(Float, nullable=True)
    cost_delta = Column(Float, nullable=True, default=0.0)

    # Phase 31: per-strategy recovery fields
    # strategy records which of the 8 CDRP-v2 recovery strategies was applied;
    # attributed_step_id names the step Attribution blamed so recovery
    # effectiveness can be measured per (strategy, attributed_step) pair.
    strategy = Column(String(64), nullable=True)
    attributed_step_id = Column(String(32), nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    original_step = relationship("WorkflowStep", foreign_keys=[original_step_id])
    new_step = relationship("WorkflowStep", foreign_keys=[new_step_id])


class FailureAttribution(Base):
    """
    Phase 30: Persists one attribution row per failed run.

    Records the suspect step, failure category from the closed taxonomy,
    confidence in the attribution, and the evidence chain that produced it.
    Exposes blame to the UI and to the replanner so recovery can be
    strategy-specific rather than always substituting the last step.
    """
    __tablename__ = "failure_attributions"

    id = Column(String(64), primary_key=True, default=lambda: f"attr_{uuid.uuid4().hex[:12]}")
    plan_id = Column(String(64), ForeignKey("workflow_plans.id"), nullable=False, index=True)

    # The step judged to be the root cause
    suspect_step_id = Column(String(32), nullable=False)
    suspect_capability = Column(String(64), nullable=False)

    # Closed failure taxonomy (see app/supervisor/attribution.py::FAILURE_CATEGORIES)
    failure_category = Column(String(64), nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)

    # JSON-encoded list[str] of human-readable evidence strings
    evidence_json = Column(Text, nullable=False, default="[]")

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    plan = relationship("WorkflowPlan")

    __table_args__ = (
        Index("ix_failure_attributions_plan", "plan_id"),
    )
