"""
Persisted Routing Decision Record model (AMOF-X Phase 3).

Stores structured routing decision telemetry for each workflow step that calls
runtime_service.generate(), enabling post-hoc auditing of privacy non-leakage
claims and calibration of predicted vs actual quality/latency/cost.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class RoutingDecisionRecord(Base):
    __tablename__ = "routing_decisions"

    id = Column(String(64), primary_key=True, default=lambda: f"rdec_{uuid.uuid4().hex[:12]}")
    workflow_step_id = Column(String(64), ForeignKey("workflow_steps.id"), nullable=False, index=True)

    placement = Column(String(32), nullable=False)
    model = Column(String(128), nullable=False)
    privacy_label = Column(String(32), nullable=False)

    classification_confidence = Column(Float, nullable=False, default=1.0)
    classification_stage = Column(String(64), nullable=True)

    predicted_quality = Column(Float, nullable=False, default=0.0)
    predicted_latency_ms = Column(Float, nullable=False, default=0.0)
    predicted_cost_usd = Column(Float, nullable=False, default=0.0)

    risk = Column(Float, nullable=False, default=0.0)
    routing_confidence = Column(Float, nullable=False, default=1.0)
    constraint_binding = Column(Boolean, nullable=False, default=False)
    reason = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    step = relationship("WorkflowStep", backref="routing_decisions")
