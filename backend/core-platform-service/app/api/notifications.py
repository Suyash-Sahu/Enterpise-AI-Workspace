import time
from fastapi import APIRouter
from app.utils.response import success_response

router = APIRouter(
    prefix="/notifications",
    tags=["Notifications Telemetry"],
)


@router.get("")
def get_notifications():
    start_time = time.time()
    notifications_data = {
        "count": 3,
        "items": [
            {
                "id": "notif-1",
                "type": "gmail",
                "title": "2 Urgent emails from Google Workspace",
                "time": "10 minutes ago",
                "read": False,
            },
            {
                "id": "notif-2",
                "type": "ai",
                "title": "Document RAG Indexing complete (148 files)",
                "time": "1 hour ago",
                "read": False,
            },
            {
                "id": "notif-3",
                "type": "workspace",
                "title": "Google Drive OAuth Token refreshed successfully",
                "time": "3 hours ago",
                "read": True,
            },
        ],
    }

    return success_response(
        data=notifications_data,
        message="Notifications retrieved successfully",
        start_time=start_time,
    )
