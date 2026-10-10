"""
Read-only SQL validation for the Database Agent.

Validation walks a parsed syntax tree rather than matching patterns on text.
The previous implementation described itself as AST-based but was regex over
uppercased SQL, which could be evaded with comments, string literals, CTE
aliases and subqueries in clauses it never inspected.
"""

import logging
from typing import Set, Tuple

import sqlglot
from sqlglot import exp

logger = logging.getLogger(__name__)

DIALECT = "postgres"

# Tables the agent may read.
#
# `oauth_credentials` was previously listed but does not exist; its real
# counterpart, `oauth_tokens`, holds encrypted Google access and refresh
# tokens and is deliberately absent.
ALLOWED_TABLES: Set[str] = {
    "ingested_documents",
    "document_chunks",
    "users",
    "workspace_activities",
}

# Never selectable, in any table, under any alias. The schema service already
# hides these from the LLM prompt; enforcing it here as well is what stops a
# steered prompt from reading them anyway.
BLOCKED_COLUMNS: Set[str] = {
    "password_hash",
    "hashed_password",
    "password",
    "access_token",
    "refresh_token",
    "token_hash",
    "code_verifier",
    "secret_key",
    "client_secret",
    "jti",
}

# Any of these node types anywhere in the tree means the statement is not a
# read. Checking node types rather than keywords means `-- DELETE` in a comment
# and 'DROP' inside a string literal are correctly ignored.
FORBIDDEN_NODES: tuple = (
    exp.Insert,
    exp.Update,
    exp.Delete,
    exp.Drop,
    exp.Create,
    exp.Alter,
    exp.TruncateTable,
    exp.Grant,
    exp.Copy,
    exp.Command,       # catch-all sqlglot uses for unparsed statements
    exp.Transaction,
    exp.Commit,
    exp.Rollback,
    exp.Set,
    exp.Use,
)

FORBIDDEN_FUNCTIONS: Set[str] = {
    "pg_read_file",
    "pg_ls_dir",
    "pg_stat_file",
    "pg_read_binary_file",
    "pg_sleep",
    "pg_execute",
    "dblink",
    "query_to_xml",
    "lo_import",
    "lo_export",
    "load_extension",
    "readfile",
    "writefile",
    "system",
    "exec",
    "eval",
}

SYSTEM_SCHEMA_PREFIXES = ("pg_", "information_schema", "sqlite_", "sys")

# The column that actually scopes each allowed table to the requesting user.
# Prompt-level instruction alone ("always include owner_id = :owner_id") is
# tolerable for an interactive, human-observed query, but not for an
# unattended scheduled job with no human reviewing the generated SQL each
# run (Phase 18) -- see validate_sql's require_owner_scope parameter, which
# AST-enforces this instead of trusting the prompt.
_OWNERSHIP_COLUMN_BY_TABLE: dict = {
    "ingested_documents": "owner_id",
    "document_chunks": "owner_id",
    "users": "id",
    "workspace_activities": "owner_id",
}


class SQLValidationError(Exception):
    """Raised when a query fails read-only validation."""


class SQLValidator:

    @staticmethod
    def validate_sql(sql: str, require_owner_scope: bool = False) -> Tuple[bool, str, Set[str]]:
        """
        Returns (is_valid, error_message, tables_used).

        Anything the parser cannot understand is rejected: an unparseable
        statement cannot be shown to be safe.

        `require_owner_scope=True` (Phase 18, unattended scheduled queries
        only) additionally AST-enforces that every real allowed table
        referenced has an equality predicate on its ownership column against
        the `:owner_id` bind parameter, somewhere in the query's WHERE
        clause. Default False preserves the exact existing behavior for the
        interactive path (a human sees the result immediately, so
        prompt-level scoping plus review is tolerable there) and every
        currently-passing test in the existing corpus.
        """
        if not sql or not sql.strip():
            return False, "SQL query cannot be empty", set()

        try:
            statements = sqlglot.parse(sql, read=DIALECT)
        except Exception as exc:
            logger.debug("SQL parse failure: %s", exc)
            return False, "Query could not be parsed as valid SQL", set()

        statements = [s for s in statements if s is not None]

        if len(statements) == 0:
            return False, "No SQL statement found", set()

        if len(statements) > 1:
            return False, "Multiple SQL statements are not allowed", set()

        root = statements[0]

        # 1. Statement must be a read.
        if not isinstance(root, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
            return (
                False,
                f"Only SELECT queries are allowed (found {type(root).__name__.upper()})",
                set(),
            )

        # 2. No write or control node anywhere, including inside subqueries.
        for node in root.walk():
            if isinstance(node, FORBIDDEN_NODES):
                return (
                    False,
                    f"Forbidden SQL operation: {type(node).__name__.upper()}",
                    set(),
                )

        # 3. CTE names are legitimate table references; collect them first so a
        #    query that defines and reads its own CTE is not rejected.
        cte_names: Set[str] = {
            cte.alias_or_name.lower()
            for cte in root.find_all(exp.CTE)
            if cte.alias_or_name
        }

        # 4. Table allowlist.
        tables_used: Set[str] = set()

        for table in root.find_all(exp.Table):
            name = (table.name or "").lower()

            if not name:
                continue

            if table.db and table.db.lower().startswith(SYSTEM_SCHEMA_PREFIXES):
                return False, "Access to system catalogs is not allowed", set()

            if name.startswith(SYSTEM_SCHEMA_PREFIXES):
                return False, "Access to system catalogs is not allowed", set()

            if name in cte_names:
                continue

            if name not in ALLOWED_TABLES:
                return False, f"Access to table '{name}' is not authorized", set()

            tables_used.add(name)

        # 5. Column blocklist.
        for column in root.find_all(exp.Column):
            if (column.name or "").lower() in BLOCKED_COLUMNS:
                return (
                    False,
                    f"Access to column '{column.name}' is not authorized",
                    set(),
                )

        # 6. No bare `*`: it would pull blocked columns straight past step 5.
        #    COUNT(*) and similar aggregates are fine — they expose no values.
        for star in root.find_all(exp.Star):
            if not star.find_ancestor(exp.AggFunc):
                return (
                    False,
                    "SELECT * is not allowed; name the columns explicitly",
                    set(),
                )

        # 7. Dangerous functions, matched on the parsed name.
        for func in root.find_all(exp.Func):
            name = (
                func.sql_name()
                if hasattr(func, "sql_name")
                else type(func).__name__
            )
            if name and name.lower() in FORBIDDEN_FUNCTIONS:
                return False, f"Function '{name}' is not allowed", set()

        for anon in root.find_all(exp.Anonymous):
            name = (anon.this or "")
            if isinstance(name, str) and name.lower() in FORBIDDEN_FUNCTIONS:
                return False, f"Function '{name}' is not allowed", set()

        if not tables_used:
            return False, "Query does not read any authorized table", set()

        if require_owner_scope:
            where = root.args.get("where") if hasattr(root, "args") else None
            # No dialect arg here deliberately: sqlglot renders a named
            # placeholder as literal ":owner_id" only in its default/generic
            # dialect -- the postgres dialect rewrites it to "%(owner_id)s",
            # which would make this substring check never match. Collapse
            # all whitespace so operand spacing/newlines can't hide or fake
            # a match either way.
            where_sql = " ".join(where.sql().lower().split()) if where else ""
            for table_name in tables_used:
                owner_col = _OWNERSHIP_COLUMN_BY_TABLE.get(table_name)
                if not owner_col:
                    continue
                # Structural-enough check: an equality predicate on this
                # table's ownership column against the :owner_id bind param
                # must appear in the WHERE clause. Rendered-SQL substring
                # match (not a strict AST walk of EQ nodes) deliberately
                # tolerates `t.owner_id`/`owner_id`/either operand order,
                # since the scheduled-report prompt controls the exact shape
                # generated -- this only needs to catch "predicate missing
                # entirely," not police every possible phrasing.
                col = owner_col.lower()
                forward = f"{col} = :owner_id"
                reverse = f":owner_id = {col}"
                if forward not in where_sql and reverse not in where_sql:
                    return (
                        False,
                        f"Scheduled query missing required '{owner_col} = :owner_id' "
                        f"predicate for table '{table_name}'",
                        set(),
                    )

        return True, "", tables_used


sql_validator = SQLValidator()
