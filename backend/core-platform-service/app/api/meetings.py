"""
Meeting API Router (AMOF-X Phase 7).

Extraction is dispatched through the real execution path
(execution_manager -> TaskRegistry's "meeting.extract"), not called
directly, so it goes through the same audit trail every other capability
does. Task creation from an action item is a second, explicit call into
"workgraph.create_task" -- the opt-in step PHASE_07.md requires, never
automatic.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.execution import ExecutionRequest
from app.schemas.meeting import (
    BulkCreateTaskResult,
    BulkCreateTasksFromActionItemsRequest,
    BulkCreateTasksResponse,
    CreateTaskFromActionItemRequest,
    MeetingCreate,
    MeetingResponse,
)
from app.schemas.workgraph import TaskResponse
from app.services.execution_manager import execution_manager
from app.services.meeting_service import meeting_service
from app.services.workgraph_service import workgraph_service

router = APIRouter(prefix="/meetings", tags=["Meetings"])

FOLLOW_UP_WINDOW_DAYS = 3


# Declared before /{meeting_id} so FastAPI's definition-order matching doesn't
# swallow this literal path as meeting_id="follow-ups" (same reasoning as
# automations.py's /from-text route).
@router.get("/follow-ups", response_model=list[TaskResponse])
def list_meeting_follow_ups(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tasks that came from a meeting action item and are overdue or due within
    FOLLOW_UP_WINDOW_DAYS, and not yet done -- Meeting -> Task -> Follow-up's
    surfacing step. Reuses workgraph_service.list_tasks' existing
    owner-scoping, just filtered to source_type="meeting_action_item".
    """
    owner_id = str(current_user.id)
    tasks = workgraph_service.list_tasks(db=db, owner_id=owner_id, source_type="meeting_action_item")
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=FOLLOW_UP_WINDOW_DAYS)

    due_soon = []
    for task in tasks:
        if task.status == "done" or task.due_date is None:
            continue
        due_date = task.due_date if task.due_date.tzinfo else task.due_date.replace(tzinfo=timezone.utc)
        if due_date < horizon:
            due_soon.append(task)

    return [workgraph_service.to_response_dto(db, t) for t in due_soon]


@router.post("", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
def create_meeting(
    data: MeetingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owner_id = str(current_user.id)

    res = execution_manager.execute(
        db=db,
        request=ExecutionRequest(
            task_type="meeting.extract",
            input={
                "transcript_text": data.transcript_text,
                "transcript_source": data.transcript_source,
            },
        ),
        owner_id=owner_id,
    )

    if res.status.value != "COMPLETED" or not res.result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=res.error_message or "Meeting extraction failed",
        )

    meeting = meeting_service.get_meeting(db=db, owner_id=owner_id, meeting_id=res.result["meeting_id"])
    return meeting_service.to_response_dto(db, meeting)


@router.get("/{meeting_id}", response_model=MeetingResponse)
def get_meeting(
    meeting_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    meeting = meeting_service.get_meeting(db=db, owner_id=str(current_user.id), meeting_id=meeting_id)
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found or access denied")
    return meeting_service.to_response_dto(db, meeting)


@router.post("/{meeting_id}/action-items/{item_id}/create-task", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task_from_action_item(
    meeting_id: str,
    item_id: str,
    data: CreateTaskFromActionItemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owner_id = str(current_user.id)

    meeting = meeting_service.get_meeting(db=db, owner_id=owner_id, meeting_id=meeting_id)
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found or access denied")

    item = meeting_service.get_action_item(db=db, meeting_id=meeting_id, item_id=item_id)
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Action item '{item_id}' not found on this meeting")

    if item.workgraph_task_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This action item already has a linked task")

    res = execution_manager.execute(
        db=db,
        request=ExecutionRequest(
            task_type="workgraph.create_task",
            input={
                "title": item.description,
                "assignee": data.assignee or item.owner,
                "project_id": data.project_id,
                "priority": data.priority,
                "created_by": "ai",
                "source_type": "meeting_action_item",
                "source_ref": meeting_id,
            },
        ),
        owner_id=owner_id,
    )

    if res.status.value != "COMPLETED" or not res.result:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=res.error_message or "Task creation from action item failed",
        )

    task_id = res.result["id"]
    meeting_service.link_action_item_task(db, item, task_id)

    task = workgraph_service.get_task(db=db, owner_id=owner_id, task_id=task_id)
    return workgraph_service.to_response_dto(db, task)


@router.post("/{meeting_id}/action-items/create-tasks", response_model=BulkCreateTasksResponse, status_code=status.HTTP_200_OK)
def create_tasks_from_all_action_items(
    meeting_id: str,
    data: BulkCreateTasksFromActionItemsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Bulk variant of create_task_from_action_item (Phase 15): reuses the exact
    same per-item creation + dedupe logic, one item at a time, so a failure
    on one item can never roll back or duplicate work already committed for
    another (each item's execution_manager.execute + link_action_item_task
    commits independently, same as the single-item endpoint).
    """
    owner_id = str(current_user.id)

    meeting = meeting_service.get_meeting(db=db, owner_id=owner_id, meeting_id=meeting_id)
    if not meeting:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Meeting '{meeting_id}' not found or access denied")

    items = meeting_service.list_action_items(db=db, meeting_id=meeting_id)
    results: list[BulkCreateTaskResult] = []

    for item in items:
        if item.workgraph_task_id:
            results.append(BulkCreateTaskResult(
                item_id=item.id, status="skipped_already_linked", task_id=item.workgraph_task_id,
            ))
            continue

        try:
            res = execution_manager.execute(
                db=db,
                request=ExecutionRequest(
                    task_type="workgraph.create_task",
                    input={
                        "title": item.description,
                        "assignee": item.owner,
                        "project_id": data.project_id,
                        "priority": data.priority,
                        "created_by": "ai",
                        "source_type": "meeting_action_item",
                        "source_ref": meeting_id,
                    },
                ),
                owner_id=owner_id,
            )
            if res.status.value != "COMPLETED" or not res.result:
                results.append(BulkCreateTaskResult(
                    item_id=item.id, status="failed",
                    error=res.error_message or "Task creation from action item failed",
                ))
                continue

            task_id = res.result["id"]
            meeting_service.link_action_item_task(db, item, task_id)
            results.append(BulkCreateTaskResult(item_id=item.id, status="created", task_id=task_id))
        except Exception as exc:
            results.append(BulkCreateTaskResult(item_id=item.id, status="failed", error=str(exc)))

    return BulkCreateTasksResponse(results=results)
