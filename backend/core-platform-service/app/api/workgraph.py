"""
WorkGraph API Router (AMOF-X Phase 6).
"""

from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.workgraph import (
    ActivityResponse,
    BoardResponse,
    CommentCreate,
    CommentResponse,
    CommentUpdate,
    DashboardResponse,
    LinksResponse,
    ProjectStats,
    DependencyCreate,
    DependencyResponse,
    ProjectCreate,
    ProjectResponse,
    ProjectUpdate,
    TaskCreate,
    TaskResponse,
    TaskUpdate,
)
from app.services.workgraph_service import workgraph_service


router = APIRouter(
    prefix="/workgraph",
    tags=["WorkGraph"],
)


# ============================================================================
# PROJECTS
# ============================================================================

@router.get(
    "/projects",
    response_model=list[ProjectResponse],
)
def list_projects(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return workgraph_service.list_projects(
        db=db,
        owner_id=str(current_user.id),
    )


@router.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_project(
    data: ProjectCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return workgraph_service.create_project(
        db=db,
        owner_id=str(current_user.id),
        name=data.name,
        description=data.description,
    )


@router.get(
    "/projects/{project_id}",
    response_model=ProjectResponse,
)
def get_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = workgraph_service.get_project(
        db=db,
        owner_id=str(current_user.id),
        project_id=project_id,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project


@router.patch(
    "/projects/{project_id}",
    response_model=ProjectResponse,
)
def update_project(
    project_id: str,
    data: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    project = workgraph_service.update_project(
        db=db,
        owner_id=str(current_user.id),
        project_id=project_id,
        name=data.name,
        description=data.description,
        status=data.status,
    )

    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project not found",
        )

    return project



@router.get("/projects/{project_id}/stats", response_model=ProjectStats)
def project_stats(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stats = workgraph_service.project_stats(db, str(current_user.id), project_id)
    if stats is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return stats


@router.get("/projects/{project_id}/board", response_model=BoardResponse)
def project_board(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    columns = workgraph_service.board(db, str(current_user.id), project_id)
    if columns is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return BoardResponse(
        project_id=project_id,
        columns={k: [workgraph_service.to_response_dto(db, t) for t in v] for k, v in columns.items()},
    )


@router.get("/dashboard", response_model=DashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = workgraph_service.dashboard(db, str(current_user.id))
    return DashboardResponse(
        counts=d["counts"],
        **{k: [workgraph_service.to_response_dto(db, t) for t in d[k]]
           for k in ("due_today", "overdue", "recently_updated")},
    )


# ============================================================================
# TASKS
# ============================================================================

@router.post(
    "/tasks",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    data: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        task = workgraph_service.create_task(
            db=db,
            owner_id=str(current_user.id),
            title=data.title,
            description=data.description,
            project_id=data.project_id,
            assignee=data.assignee,
            priority=data.priority,
            status=data.status,
            type=data.type,
            due_date=data.due_date,
            created_by="human",
            created_by_actor=f"user:{current_user.id}",
            source_type="manual",
            depends_on=data.depends_on,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return workgraph_service.to_response_dto(
        db,
        task,
    )


@router.get(
    "/tasks",
    response_model=list[TaskResponse],
)
def list_tasks(
    project_id: Optional[str] = Query(
        default=None,
    ),

    status_filter: Optional[str] = Query(
        default=None,
        alias="status",
    ),

    assignee: Optional[str] = Query(
        default=None,
        description='Exact assignee, or "me" for the authenticated user (email).',
    ),

    priority: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    due_before: Optional[datetime] = Query(default=None),
    due_after: Optional[datetime] = Query(default=None),
    overdue: bool = Query(default=False),

    db: Session = Depends(get_db),

    current_user: User = Depends(
        get_current_user
    ),

    search: Optional[str] = Query(default=None),
):
    tasks = workgraph_service.list_tasks(
        db=db,
        owner_id=str(current_user.id),
        project_id=project_id,
        status=status_filter,
        assignee=(current_user.email if assignee == "me" else assignee),
        search=search,
        priority=priority,
        type=type,
        due_before=due_before,
        due_after=due_after,
        overdue=overdue,
    )

    return [
        workgraph_service.to_response_dto(
            db,
            task,
        )
        for task in tasks
    ]


@router.post(
    "/tasks/{task_id}/dependencies",
    response_model=DependencyResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_dependency(
    task_id: str,
    data: DependencyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        dependency = workgraph_service.add_dependency(
            db=db,
            owner_id=str(current_user.id),
            task_id=task_id,
            depends_on_task_id=data.depends_on_task_id,
            kind=data.kind,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return DependencyResponse(
        task_id=dependency.task_id,
        depends_on_task_id=dependency.depends_on_task_id,
        kind=dependency.kind,
    )

@router.get(
    "/tasks/{task_id}/dependencies",
    response_model=list[DependencyResponse],
)
def list_dependencies(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        dependencies = (
            workgraph_service.list_dependencies(
                db=db,
                owner_id=str(current_user.id),
                task_id=task_id,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    return [
        DependencyResponse(
            task_id=item.task_id,
            depends_on_task_id=item.depends_on_task_id,
            kind=item.kind,
        )
        for item in dependencies
    ]

@router.delete(
    "/tasks/{task_id}/dependencies/{depends_on_task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_dependency(
    task_id: str,
    depends_on_task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        removed = workgraph_service.remove_dependency(
            db=db,
            owner_id=str(current_user.id),
            task_id=task_id,
            depends_on_task_id=depends_on_task_id,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc

    if not removed:
        raise HTTPException(
            status_code=404,
            detail="Dependency not found.",
        )
@router.get("/tasks/{task_id}/links", response_model=LinksResponse)
def task_links(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return workgraph_service.get_links(db, str(current_user.id), task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/tasks/{task_id}/activity", response_model=list[ActivityResponse])
def task_activity(
    task_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return workgraph_service.list_activity(db, str(current_user.id), task_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ============================================================================
# GET SINGLE TASK
# ============================================================================

@router.get(
    "/tasks/{task_id}",
    response_model=TaskResponse,
)
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = workgraph_service.get_task(
        db=db,
        owner_id=str(current_user.id),
        task_id=task_id,
    )

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Task '{task_id}' "
                "not found or access denied"
            ),
        )

    return workgraph_service.to_response_dto(
        db,
        task,
    )


# ============================================================================
# UPDATE TASK
# ============================================================================

@router.patch(
    "/tasks/{task_id}",
    response_model=TaskResponse,
)
def update_task(
    task_id: str,
    data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        task = workgraph_service.update_task(
            db=db,
            owner_id=str(current_user.id),
            task_id=task_id,
            **data.model_dump(
                exclude_unset=True
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"Task '{task_id}' "
                "not found or access denied"
            ),
        )

    return workgraph_service.to_response_dto(
        db,
        task,
    )

# ============================================================================
# COMMENTS (single-owner)
# ============================================================================

def _comment_dto(c) -> CommentResponse:
    dto = CommentResponse.model_validate(c)
    dto.edited = bool(c.updated_at and c.created_at and c.updated_at > c.created_at)
    return dto


@router.get("/tasks/{task_id}/comments", response_model=list[CommentResponse])
def list_comments(
    task_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        comments = workgraph_service.list_comments(db, str(current_user.id), task_id, limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return [_comment_dto(c) for c in comments]


@router.post(
    "/tasks/{task_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_comment(
    task_id: str,
    data: CommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        comment = workgraph_service.create_comment(db, str(current_user.id), task_id, data.body)
    except ValueError as exc:
        raise HTTPException(status_code=404 if "not found" in str(exc) else 400, detail=str(exc)) from exc
    return _comment_dto(comment)


@router.patch("/comments/{comment_id}", response_model=CommentResponse)
def edit_comment(
    comment_id: str,
    data: CommentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        comment = workgraph_service.update_comment(db, str(current_user.id), comment_id, data.body)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if comment is None:
        raise HTTPException(status_code=404, detail="Comment not found")
    return _comment_dto(comment)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_comment(
    comment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not workgraph_service.delete_comment(db, str(current_user.id), comment_id):
        raise HTTPException(status_code=404, detail="Comment not found")
