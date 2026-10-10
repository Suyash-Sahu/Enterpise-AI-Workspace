import time

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.agents.database_agent import database_agent
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.user import User
from app.schemas.database_agent import (
    DatabaseQueryRequest,
    DatabaseResult,
    DatabaseSchemaResponse,
    DatabaseSQLRequest,
)
from app.services.database_schema_service import database_schema_service
from app.utils.response import success_response

router = APIRouter()


@router.post("/query")
@limiter.limit(settings.RATE_LIMIT_EXPENSIVE)
def query_database(
    request: Request,
    payload: DatabaseQueryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Natural-language to SQL query endpoint.

    Converts the question to a read-only SELECT, validates it against the
    allowed tables and columns, executes it, and returns a grounded
    explanation. Rate limited because each call costs an LLM round-trip.
    """
    start_time = time.time()

    try:
        result: DatabaseResult = database_agent.process_query(
            db=db,
            question=payload.question,
            # Tenancy comes from the token, never from the request body.
            owner_id=str(current_user.id),
            limit=payload.limit or settings.DB_AGENT_DEFAULT_LIMIT,
        )
    except ValueError as exc:
        # Validation rejections are the caller's problem and safe to surface.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return success_response(
        data=result.model_dump(),
        message="Database query executed successfully",
        start_time=start_time,
    )


@router.post("/sql")
@limiter.limit(settings.RATE_LIMIT_EXPENSIVE)
def execute_developer_sql(
    request: Request,
    payload: DatabaseSQLRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Developer read-only SQL endpoint, gated by DB_AGENT_RAW_SQL_ENABLED.

    Restricted to the 'admin' role: this accepts arbitrary SQL text, so being
    signed in is not sufficient authorization to reach it.
    """
    start_time = time.time()

    if not settings.DB_AGENT_RAW_SQL_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Raw SQL execution is disabled in this environment",
        )

    role_name = current_user.role.name if current_user.role else None

    if role_name != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Raw SQL execution requires the admin role",
        )

    try:
        result = database_agent.process_developer_sql(
            db=db,
            sql=payload.sql,
            owner_id=str(current_user.id),
            limit=payload.limit or settings.DB_AGENT_DEFAULT_LIMIT,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return success_response(
        data=result.model_dump(),
        message="Developer SQL executed successfully",
        start_time=start_time,
    )


@router.get("/schema")
def get_database_schema(
    current_user: User = Depends(get_current_user),
):
    """Allowed table and column schemas for the Database Agent."""
    start_time = time.time()

    schema_data: DatabaseSchemaResponse = (
        database_schema_service.get_allowed_schema()
    )

    return success_response(
        data=schema_data.model_dump(),
        message="Database allowed schema retrieved successfully",
        start_time=start_time,
    )


@router.get("/health")
def database_agent_health(
    current_user: User = Depends(get_current_user),
):
    """Database Agent telemetry."""
    start_time = time.time()

    schema_obj = database_schema_service.get_allowed_schema()

    return success_response(
        data={
            "status": "online",
            "db_agent_enabled": settings.DB_AGENT_ENABLED,
            "raw_sql_enabled": settings.DB_AGENT_RAW_SQL_ENABLED,
            "allowed_tables_count": len(schema_obj.tables),
            "query_timeout_seconds": settings.DB_AGENT_QUERY_TIMEOUT,
            "max_limit": settings.DB_AGENT_MAX_LIMIT,
        },
        message="Database Agent is operational",
        start_time=start_time,
    )
