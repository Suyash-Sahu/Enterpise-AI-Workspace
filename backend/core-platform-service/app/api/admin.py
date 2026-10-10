from fastapi import APIRouter, Depends

from app.core.rbac import require_role

router = APIRouter(
    prefix="/admin",
    tags=["Admin"],
)


@router.get("/dashboard")
def dashboard(
    user=Depends(require_role("admin")),
):
    return {
        "message": f"Welcome {user.name}"
    }


from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.execution import Execution
from app.models.routing_decision import RoutingDecisionRecord
from app.models.workflow import WorkflowPlan, ReplanningEvent


@router.get("/telemetry")
def get_telemetry(
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    """
    Returns real empirical production telemetry summary aggregated from the database.
    """
    total_executions = db.query(Execution).count()
    completed_executions = db.query(Execution).filter(Execution.status == "COMPLETED").count()
    failed_executions = db.query(Execution).filter(Execution.status == "FAILED").count()
    total_routing_decisions = db.query(RoutingDecisionRecord).count()
    total_replanning_events = db.query(ReplanningEvent).count()
    total_workflow_plans = db.query(WorkflowPlan).count()

    return {
        "telemetry_source": "EMPIRICAL_DB",
        "total_executions": total_executions,
        "completed_executions": completed_executions,
        "failed_executions": failed_executions,
        "total_routing_decisions": total_routing_decisions,
        "total_replanning_events": total_replanning_events,
        "total_workflow_plans": total_workflow_plans,
    }