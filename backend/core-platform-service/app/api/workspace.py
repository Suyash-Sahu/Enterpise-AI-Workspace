import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.services.workspace_service import WorkspaceService
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.utils.response import success_response, error_response

router = APIRouter(
    prefix="/workspace",
    tags=["Workspace"],
)


@router.get("/dashboard")
@router.get("")
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()
    try:
        data = WorkspaceService.get_dashboard(db=db, user_id=current_user.id)
        return success_response(
            data=data,
            message="Workspace dashboard metrics fetched successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Request failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.get("/summary")
def workspace_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()
    try:
        data = WorkspaceService.summary(db=db, user_id=current_user.id)
        return success_response(
            data=data,
            message="Workspace summary fetched successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Request failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )