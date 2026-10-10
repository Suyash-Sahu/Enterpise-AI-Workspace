import time
import logging
from typing import Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text as sql_text, exc as sql_exc

from app.core.config import settings
from app.services.sql_validator import SQLValidator

logger = logging.getLogger(__name__)


class DatabaseQueryTimeoutError(Exception):
    """Exception raised when database statement timeout is exceeded."""


class DatabaseQueryService:

    @staticmethod
    def execute_read_only_query(
        db: Session,
        sql: str,
        owner_id: str,
        limit: int = 20,
        params: dict[str, Any] | None = None,
    ) -> Tuple[list[str], list[dict[str, Any]], float]:
        """
        Executes a validated read-only SQL query against PostgreSQL / database backend.

        Security Measures:
        1. Validates SQL structure using SQLValidator.
        2. Sets database-side read-only transaction: SET TRANSACTION READ ONLY.
        3. Sets database-side statement timeout: SET LOCAL statement_timeout = 5000.
        4. Binds owner_id parameter securely (:owner_id).
        5. Caps LIMIT <= settings.DB_AGENT_MAX_LIMIT (100).
        """
        # 1. AST Validation
        is_valid, error_msg, tables_used = SQLValidator.validate_sql(sql)
        if not is_valid:
            raise ValueError(f"SQL Security Validation Error: {error_msg}")

        # 2. Limit capping
        capped_limit = min(max(1, limit), settings.DB_AGENT_MAX_LIMIT)

        # Ensure parameters dictionary exists
        bind_params = params.copy() if params else {}
        bind_params["owner_id"] = str(owner_id)
        bind_params["limit_val"] = capped_limit

        # If LIMIT isn't in SQL, append LIMIT :limit_val
        clean_sql = sql.rstrip(";").strip()
        if "LIMIT" not in clean_sql.upper():
            clean_sql = f"{clean_sql} LIMIT :limit_val"

        start_time = time.time()

        try:
            # 3. Database-side read-only transaction & statement timeout.
            #    The docstring above previously promised the read-only
            #    transaction but the statement was never issued, leaving the
            #    validator as the only thing between generated SQL and the
            #    database. It is now actually set.
            dialect_name = db.bind.dialect.name if db.bind else "postgresql"

            if dialect_name == "postgresql":
                timeout_ms = int(settings.DB_AGENT_QUERY_TIMEOUT * 1000)

                # A literal is required here (SET does not accept bind
                # parameters); the value is an int derived from config, never
                # from user input.
                db.execute(
                    sql_text(f"SET LOCAL statement_timeout = {timeout_ms}")
                )
                db.execute(sql_text("SET TRANSACTION READ ONLY"))

            # 4. Parameterized query execution
            result = db.execute(sql_text(clean_sql), bind_params)
            columns = list(result.keys()) if result.returns_rows else []
            rows_raw = result.fetchall() if result.returns_rows else []

            # 5. Format row dictionaries
            rows: list[dict[str, Any]] = []
            for row in rows_raw:
                row_dict = {}
                for col, val in zip(columns, row):
                    # JSON serialization normalization
                    if hasattr(val, "isoformat"):
                        row_dict[col] = val.isoformat()
                    elif hasattr(val, "__str__") and not isinstance(val, (int, float, bool, list, dict)):
                        row_dict[col] = str(val)
                    else:
                        row_dict[col] = val
                rows.append(row_dict)

            execution_time = round(time.time() - start_time, 3)
            # Rollback/commit to release the read-only transaction mode on the session
            db.rollback()
            return columns, rows, execution_time

        except sql_exc.OperationalError as oe:
            db.rollback()
            if "timeout" in str(oe).lower():
                raise DatabaseQueryTimeoutError(f"Database query exceeded timeout of {settings.DB_AGENT_QUERY_TIMEOUT} seconds")
            raise ValueError(f"Database query operational failure: {str(oe)}")
        except Exception as e:
            db.rollback()
            logger.error(f"Database Query Service Execution Error: {e}")
            raise ValueError(f"Database query execution failed: {str(e)}")


database_query_service = DatabaseQueryService()
