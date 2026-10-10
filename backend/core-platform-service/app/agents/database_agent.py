import logging
from sqlalchemy.orm import Session

from app.schemas.database_agent import DatabaseResult
from app.services.sql_generation_service import sql_generation_service
from app.services.sql_validator import SQLValidator
from app.services.database_query_service import database_query_service
from app.services.database_result_service import database_result_service

logger = logging.getLogger(__name__)


class DatabaseAgent:

    @staticmethod
    def process_query(
        db: Session,
        question: str,
        owner_id: str,
        limit: int = 20,
        enforce_owner_scope: bool = False,
    ) -> DatabaseResult:
        """
        Orchestrates natural language to safe database query pipeline:
        1. Generates parameterized SQL via AIService.
        2. Validates SQL AST and table allowlists via SQLValidator.
        3. Executes read-only query with database-side timeout & tenant isolation.
        4. Generates grounded explanation & logs audit entry.

        `enforce_owner_scope=True` (Phase 18) additionally AST-enforces the
        owner_id/id predicate -- used by the unattended scheduled report
        path (DatabaseReportHandler), where no human reviews the generated
        SQL each run. Default False keeps the interactive path unchanged.
        """
        # 1. Generate SQL
        sql, sql_response = sql_generation_service.generate_sql(question)

        # 2. AST Validation & Table extraction
        is_valid, error_msg, tables_used = SQLValidator.validate_sql(sql, require_owner_scope=enforce_owner_scope)
        if not is_valid:
            logger.warning(f"DatabaseAgent blocked invalid generated SQL: '{sql}' Error: {error_msg}")
            # Fallback safe query if generated SQL failed security AST validation
            sql = "SELECT source, chunk_count FROM ingested_documents WHERE owner_id = :owner_id"
            tables_used = {"ingested_documents"}
            # The generated SQL was rejected, so its metadata does not
            # describe what actually ran (a hardcoded fallback query, no LLM
            # involved in producing it).
            sql_response = None

        # 3. Execute read-only query
        columns, rows, execution_time = database_query_service.execute_read_only_query(
            db=db,
            sql=sql,
            owner_id=owner_id,
            limit=limit,
        )

        row_count = len(rows)

        # 4. Generate grounded explanation
        explanation, explanation_response = database_result_service.generate_explanation(
            question=question,
            sql=sql,
            rows=rows,
            row_count=row_count,
        )

        # 5. Audit log
        database_result_service.log_query_audit(
            user_id=owner_id,
            question=question,
            sql=sql,
            tables_used=list(tables_used),
            execution_time=execution_time,
            row_count=row_count,
            success=True,
        )

        # Aggregate real LLM metadata across both generation calls (SQL +
        # explanation) into one measurement -- a research-grade token/cost
        # count for this capability must include everything it actually
        # spent, not just one of its two LLM calls (Phase 10 token audit,
        # 2026-09-20). model/provider/runtime are attributed to the SQL
        # generation call (the primary generation step) when available,
        # falling back to the explanation call's; tokens are summed.
        responses = [r for r in (sql_response, explanation_response) if r is not None]
        primary = sql_response or explanation_response

        return DatabaseResult(
            question=question,
            sql=sql,
            columns=columns,
            rows=rows,
            row_count=row_count,
            explanation=explanation,
            execution_time=execution_time,
            model=primary.model if primary else None,
            provider=primary.provider if primary else None,
            runtime=primary.runtime if primary else None,
            input_tokens=sum(r.input_tokens for r in responses) if responses else None,
            output_tokens=sum(r.output_tokens for r in responses) if responses else None,
            total_tokens=sum(r.total_tokens for r in responses) if responses else None,
        )

    @staticmethod
    def process_developer_sql(
        db: Session,
        sql: str,
        owner_id: str,
        limit: int = 20,
    ) -> DatabaseResult:
        """
        Processes developer read-only SQL directly through AST validation and database-side timeouts.
        """
        is_valid, error_msg, tables_used = SQLValidator.validate_sql(sql)
        if not is_valid:
            raise ValueError(f"Developer SQL Security Error: {error_msg}")

        columns, rows, execution_time = database_query_service.execute_read_only_query(
            db=db,
            sql=sql,
            owner_id=owner_id,
            limit=limit,
        )

        row_count = len(rows)
        explanation = f"Developer query returned {row_count} rows in {execution_time}s."

        database_result_service.log_query_audit(
            user_id=owner_id,
            question="Developer Raw SQL Execution",
            sql=sql,
            tables_used=list(tables_used),
            execution_time=execution_time,
            row_count=row_count,
            success=True,
        )

        return DatabaseResult(
            question="Developer Raw SQL",
            sql=sql,
            columns=columns,
            rows=rows,
            row_count=row_count,
            explanation=explanation,
            execution_time=execution_time,
        )


database_agent = DatabaseAgent()


# ---------------------------------------------------------------------------
# Phase 23: Agent-contract wrapper.
#
# Tools: `database_agent` (the class above) + `SQLValidator`, per
# PHASE_23.md Task 3 -- DataAgent wraps the whole existing
# DatabaseAgent.process_query pipeline (SQL generation, AST validation,
# read-only execution, grounded explanation, audit logging) rather than
# reimplementing any of it. Its own audit-log write is bookkeeping for its
# own read, the same precedent app/execution/registry.py already applies to
# meeting.extract (classified read_only despite persisting its own
# extraction record) -- see tests/test_capability_registry.py.
# ---------------------------------------------------------------------------
from pydantic import BaseModel, Field

from app.agents.base import Agent, AgentContext, AgentResult, AgentSpec


class DataAgentInput(BaseModel):
    question: str
    limit: int = 20
    enforce_owner_scope: bool = False


class RowSet(BaseModel):
    rows: list[dict] = Field(default_factory=list)
    sql: str = ""
    owner_predicate_verified: bool = False


class DataAgent(Agent):
    spec = AgentSpec(
        name="DataAgent",
        role="structured facts from the owner's DB",
        input_schema=DataAgentInput,
        output_schema=RowSet,
        tools=["database_agent", "SQLValidator"],
        reads_state=["owner_id"],
        writes_state=[],
        side_effect="read_only",
        requires_human_approval=False,
        verifier="RowSetVerifier",
    )

    def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
        assert isinstance(inputs, DataAgentInput)
        result = database_agent.process_query(
            db=ctx.db,
            question=inputs.question,
            owner_id=ctx.owner_id,
            limit=inputs.limit,
            enforce_owner_scope=inputs.enforce_owner_scope,
        )
        # The DatabaseResult object itself is preserved as `output` (not
        # re-wrapped into a bare RowSet) so ExecutionHandler callers keep
        # access to model/provider/runtime/token metadata exactly as before
        # -- RowSet above documents this agent's declared output shape, but
        # DatabaseResult is a superset of it (rows, sql, plus generation
        # metadata), never a mismatch.
        owner_verified = inputs.enforce_owner_scope or ("owner_id" in (result.sql or ""))
        return AgentResult(
            output=result,
            evidence=[result.sql] if result.sql else [],
            model=result.model,
            notes=f"owner_predicate_verified={owner_verified}",
        )


data_agent = DataAgent()
