"""
Observability API endpoints (AMOF-X Phase 10).
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.observability.tracing import trace_view_service
from app.schemas.tracing import TraceViewResponse

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/traces/{trace_id}", response_model=TraceViewResponse)
def get_trace_view(
    trace_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Returns full execution trace, plan steps, routing decisions, replanning events,
    and approvals for the given trace_id.
    """
    return trace_view_service.get_trace(db=db, trace_id=trace_id, owner_id=str(current_user.id))
