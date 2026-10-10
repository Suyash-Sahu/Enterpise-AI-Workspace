import json
import logging
from typing import Any, Optional
from app.schemas.runtime import RuntimeGenerateResponse
from app.services.ai_service import ai_service
from app.prompts.database_agent import DATABASE_EXPLANATION_PROMPT

logger = logging.getLogger(__name__)


class DatabaseResultService:

    @staticmethod
    def generate_explanation(
        question: str,
        sql: str,
        rows: list[dict[str, Any]],
        row_count: int,
    ) -> tuple[str, Optional[RuntimeGenerateResponse]]:
        """
        Generates a grounded natural language explanation of executed database query results using AIService.

        Returns (explanation, response): response is the real
        RuntimeGenerateResponse when generation happened and succeeded, or
        None when there was nothing to explain (row_count == 0, no LLM call
        made) or generation failed (Phase 10 token audit, 2026-09-20).
        """
        if row_count == 0:
            return "No matching records were found in the database for your query.", None

        # Truncate sample rows for LLM context window efficiency
        sample_rows = rows[:5]
        rows_str = json.dumps(sample_rows, default=str)

        prompt = DATABASE_EXPLANATION_PROMPT.format(
            question=question,
            sql=sql,
            row_count=row_count,
            rows_json=rows_str,
        )

        try:
            response = ai_service.generate_with_metadata(prompt)
            return (response.completion or "").strip(), response
        except Exception as e:
            logger.warning(f"Failed to generate AI explanation for database result: {e}")
            return f"Retrieved {row_count} records from database.", None

    @staticmethod
    def log_query_audit(
        user_id: str,
        question: str,
        sql: str,
        tables_used: list[str],
        execution_time: float,
        row_count: int,
        success: bool = True,
        error_type: str | None = None,
    ) -> dict[str, Any]:
        """
        Emits an auditable log entry for database agent queries.
        """
        audit_entry = {
            "user_id": user_id,
            "question": question,
            "sql": sql,
            "tables_used": tables_used,
            "execution_time": execution_time,
            "row_count": row_count,
            "success": success,
            "error_type": error_type,
        }
        logger.info(f"[DB Agent Audit Log]: user={user_id} success={success} rows={row_count} time={execution_time}s sql='{sql}'")
        return audit_entry


database_result_service = DatabaseResultService()
