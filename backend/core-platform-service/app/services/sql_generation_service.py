import re
import logging
from typing import Optional

from app.schemas.runtime import RuntimeGenerateResponse
from app.services.ai_service import ai_service
from app.services.database_schema_service import database_schema_service
from app.prompts.database_agent import DATABASE_AGENT_SYSTEM_PROMPT

logger = logging.getLogger(__name__)


class SQLGenerationService:

    # This fallback path was previously unreachable: the old code called
    # ai_service.smart_generate(), which swallows every exception internally
    # and never raises, so this except block was dead code -- any failure
    # fell through to database_agent's own (valid) AST-validation fallback
    # instead. generate_with_metadata() correctly raises on failure, which
    # made this path reachable for the first time and surfaced that it
    # referenced a column ingested_documents does not have ("created_at" --
    # the real columns are chunk_count/ingested_at, app/models/document_chunk.py).
    # Fixed to match database_agent's own equivalent fallback query.
    FALLBACK_SQL = "SELECT source, chunk_count FROM ingested_documents WHERE owner_id = :owner_id"

    @staticmethod
    def generate_sql(question: str) -> tuple[str, Optional[RuntimeGenerateResponse]]:
        """
        Translates a natural language question into a PostgreSQL SELECT query using AIService.

        Returns (sql, response): response is the real RuntimeGenerateResponse
        when generation succeeded (Phase 10 token audit, 2026-09-20 -- this
        previously went through smart_generate() and discarded the real
        model/provider/runtime/token data), or None when the fallback SQL
        below was used instead.
        """
        schema_text = database_schema_service.get_schema_summary_text()
        prompt = DATABASE_AGENT_SYSTEM_PROMPT.format(
            schema_text=schema_text,
            question=question,
        )

        try:
            response = ai_service.generate_with_metadata(prompt)
            clean_sql = (response.completion or "").strip()

            # Clean markdown codeblocks ```sql ... ```
            if "```" in clean_sql:
                matches = re.findall(r"```(?:sql)?\s*(.*?)\s*```", clean_sql, re.DOTALL | re.IGNORECASE)
                if matches:
                    clean_sql = matches[0].strip()
                else:
                    clean_sql = clean_sql.replace("```", "").strip()

            # Remove leading comments if any
            lines = [l for l in clean_sql.split("\n") if not l.strip().startswith("--")]
            clean_sql = "\n".join(lines).strip()

            return clean_sql, response
        except Exception as e:
            logger.error(f"SQL Generation AI failure: {e}")
            # Fallback simple SELECT query for graceful handling
            return SQLGenerationService.FALLBACK_SQL, None


sql_generation_service = SQLGenerationService()
