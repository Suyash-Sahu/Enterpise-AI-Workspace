import logging
from sqlalchemy import inspect
from app.db.database import engine
from app.schemas.database_agent import DatabaseSchemaResponse, DatabaseTableSchema, DatabaseColumnSchema

logger = logging.getLogger(__name__)

# Single source of truth: the validator enforces these at execution time, and
# this service uses the same sets to build the LLM prompt. Keeping two copies
# is how the prompt came to hide password_hash while the validator still
# allowed a query to select it.
from app.services.sql_validator import (  # noqa: E402
    ALLOWED_TABLES,
    BLOCKED_COLUMNS,
)


class DatabaseSchemaService:

    @staticmethod
    def get_allowed_schema() -> DatabaseSchemaResponse:
        """
        Inspects database metadata and returns schemas for allowed tables only.
        """
        inspector = inspect(engine)
        tables: list[DatabaseTableSchema] = []

        try:
            all_table_names = inspector.get_table_names()
        except Exception as e:
            logger.warning(f"Database table inspection warning: {e}")
            all_table_names = list(ALLOWED_TABLES)

        for table_name in all_table_names:
            if table_name not in ALLOWED_TABLES:
                continue

            columns: list[DatabaseColumnSchema] = []
            try:
                col_info = inspector.get_columns(table_name)
                for col in col_info:
                    cname = col["name"]
                    if cname in BLOCKED_COLUMNS:
                        continue
                    ctype = str(col["type"])
                    columns.append(DatabaseColumnSchema(name=cname, type=ctype))
            except Exception as e:
                logger.error(f"Error inspecting columns for {table_name}: {e}")

            tables.append(DatabaseTableSchema(name=table_name, columns=columns))

        return DatabaseSchemaResponse(tables=tables)

    @staticmethod
    def get_schema_summary_text() -> str:
        """
        Formats allowed tables and columns into a clean text representation for LLM prompt context.
        """
        schema_obj = DatabaseSchemaService.get_allowed_schema()
        summary_lines = []
        for tbl in schema_obj.tables:
            cols = ", ".join([f"{col.name} ({col.type})" for col in tbl.columns])
            summary_lines.append(f"Table '{tbl.name}': [{cols}]")

        return "\n".join(summary_lines)


database_schema_service = DatabaseSchemaService()
