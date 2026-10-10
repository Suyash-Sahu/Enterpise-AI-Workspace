from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.services.audit_service import log_action

router = APIRouter(
    prefix="/audit-log",
    tags=["Audit"],
)


@router.post("/")
def create_log(
    action: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    log_action(
        db=db,
        user_id=current_user.id,
        action=action,
        endpoint="/audit-log",
        method="POST",
    )

    return {
        "message": "Audit log created"
    }