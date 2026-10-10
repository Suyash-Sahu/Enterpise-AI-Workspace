from typing import Optional, Any
from pydantic import BaseModel, Field


# owner_id is deliberately absent from both request models. It was previously
# client-supplied, which let any caller name the tenant they wanted to read as.
# It is now taken from the authenticated user and never from the request body.


class DatabaseQueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language question about workspace data",
        json_schema_extra={"example": "How many documents have I indexed?"},
    )
    limit: Optional[int] = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum rows to return (capped at 100)",
    )


class DatabaseSQLRequest(BaseModel):
    sql: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="Read-only PostgreSQL SELECT query",
        json_schema_extra={
            "example": "SELECT source, chunk_count FROM ingested_documents LIMIT 10"
        },
    )
    limit: Optional[int] = Field(default=20, ge=1, le=100)


class DatabaseColumnSchema(BaseModel):
    name: str
    type: str


class DatabaseTableSchema(BaseModel):
    name: str
    columns: list[DatabaseColumnSchema]


class DatabaseSchemaResponse(BaseModel):
    tables: list[DatabaseTableSchema]


class DatabaseResult(BaseModel):
    question: Optional[str] = None
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    explanation: Optional[str] = None
    execution_time: float = 0.0
    # Real LLM metadata aggregated across the SQL-generation and explanation
    # calls (Phase 10 token audit, 2026-09-20). model/provider/runtime come
    # from the SQL-generation call (the primary generation step) when it
    # succeeded, falling back to the explanation call's if not; tokens are
    # summed across both since both are real spend for this capability. None
    # when neither call produced a real response.
    model: Optional[str] = None
    provider: Optional[str] = None
    runtime: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
