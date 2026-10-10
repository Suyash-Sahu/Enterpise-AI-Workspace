import pytest
from app.db.database import SessionLocal, engine, Base
from app.services.database_schema_service import database_schema_service
from app.services.sql_validator import SQLValidator
from app.services.database_query_service import database_query_service
from app.agents.database_agent import database_agent
from app.rag.pipeline import rag_pipeline


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_schema_discovery():
    schema = database_schema_service.get_allowed_schema()
    table_names = [t.name for t in schema.tables]
    assert "ingested_documents" in table_names
    assert "document_chunks" in table_names
    assert "passwords" not in table_names


def test_sql_validator_security():
    # 1. Valid SELECT queries
    is_valid, _, tables = SQLValidator.validate_sql("SELECT id, source FROM ingested_documents WHERE owner_id = :owner_id")
    assert is_valid is True
    assert "ingested_documents" in tables

    # 2. Rejection of DROP TABLE
    is_valid, err, _ = SQLValidator.validate_sql("DROP TABLE document_chunks")
    assert is_valid is False
    assert "Only SELECT queries are allowed" in err or "Forbidden SQL operation" in err

    # 3. Rejection of DELETE
    is_valid, err, _ = SQLValidator.validate_sql("DELETE FROM ingested_documents WHERE id = 1")
    assert is_valid is False

    # 4. Rejection of UPDATE
    is_valid, err, _ = SQLValidator.validate_sql("UPDATE users SET owner_id = '2'")
    assert is_valid is False

    # 5. Rejection of INSERT
    is_valid, err, _ = SQLValidator.validate_sql("INSERT INTO users (id) VALUES (999)")
    assert is_valid is False

    # 6. Rejection of multiple statements
    is_valid, err, _ = SQLValidator.validate_sql("SELECT * FROM ingested_documents; DROP TABLE users;")
    assert is_valid is False

    # 7. Rejection of unauthorized tables
    is_valid, err, _ = SQLValidator.validate_sql("SELECT secret FROM system_credentials")
    assert is_valid is False


def test_sql_validator_blocks_credential_columns():
    """
    Finding C10: `users` is a readable table, so without a column check a
    steered natural-language question could return password hashes.
    """
    for sql in (
        "SELECT email, password_hash FROM users",
        "SELECT u.password_hash FROM users u",
        "SELECT (SELECT password_hash FROM users LIMIT 1) AS h FROM users",
    ):
        is_valid, err, _ = SQLValidator.validate_sql(sql)
        assert is_valid is False, f"should have been rejected: {sql}"
        assert "password_hash" in err

    # `SELECT *` would pull blocked columns straight past the column check.
    is_valid, err, _ = SQLValidator.validate_sql("SELECT * FROM users")
    assert is_valid is False
    assert "SELECT *" in err

    # Aggregates over * expose no values and stay allowed.
    is_valid, _, _ = SQLValidator.validate_sql("SELECT COUNT(*) FROM users")
    assert is_valid is True


def test_sql_validator_resists_regex_evasion():
    """
    Finding H5: the previous validator matched patterns on uppercased text, so
    keywords could be smuggled past it and whole clauses went uninspected.
    """
    # Keywords inside literals and comments are data, not operations.
    is_valid, _, _ = SQLValidator.validate_sql(
        "SELECT source FROM ingested_documents WHERE source = 'DELETE FROM users'"
    )
    assert is_valid is True

    is_valid, _, _ = SQLValidator.validate_sql(
        "SELECT source FROM ingested_documents -- DROP TABLE users"
    )
    assert is_valid is True

    # Subqueries and unions are inspected, not just the top-level FROM.
    is_valid, err, _ = SQLValidator.validate_sql(
        "SELECT source FROM ingested_documents "
        "WHERE id IN (SELECT id FROM oauth_tokens)"
    )
    assert is_valid is False
    assert "oauth_tokens" in err

    is_valid, err, _ = SQLValidator.validate_sql(
        "SELECT source FROM ingested_documents UNION SELECT tablename FROM pg_tables"
    )
    assert is_valid is False

    # A CTE may be read back under its own alias.
    is_valid, _, _ = SQLValidator.validate_sql(
        "WITH recent AS (SELECT source FROM ingested_documents) SELECT source FROM recent"
    )
    assert is_valid is True

    # Anything unparseable cannot be shown to be safe.
    is_valid, _, _ = SQLValidator.validate_sql("not sql at all !!!")
    assert is_valid is False


def test_owner_scope_enforcement_is_opt_in_and_does_not_break_existing_corpus():
    """
    Phase 18: require_owner_scope defaults to False, so every currently-
    passing query in this file's corpus above -- including ones with no
    ownership predicate at all, like COUNT(*) over the whole users table --
    must keep validating exactly as before. This is the "test against the
    existing corpus first" regression check the phase's own risk section
    calls for.
    """
    is_valid, _, _ = SQLValidator.validate_sql("SELECT COUNT(*) FROM users")
    assert is_valid is True

    is_valid, _, _ = SQLValidator.validate_sql(
        "WITH recent AS (SELECT source FROM ingested_documents) SELECT source FROM recent"
    )
    assert is_valid is True

    # Same two queries under require_owner_scope=True must now be rejected --
    # neither includes an ownership predicate.
    is_valid, err, _ = SQLValidator.validate_sql("SELECT COUNT(*) FROM users", require_owner_scope=True)
    assert is_valid is False
    assert "missing required" in err

    is_valid, err, _ = SQLValidator.validate_sql(
        "WITH recent AS (SELECT source FROM ingested_documents) SELECT source FROM recent",
        require_owner_scope=True,
    )
    assert is_valid is False
    assert "missing required" in err


def test_owner_scope_enforcement_accepts_the_correct_predicate():
    """The negative test's counterpart: a query WITH the predicate must pass under require_owner_scope=True."""
    is_valid, _, tables = SQLValidator.validate_sql(
        "SELECT id, source FROM ingested_documents WHERE owner_id = :owner_id",
        require_owner_scope=True,
    )
    assert is_valid is True
    assert "ingested_documents" in tables

    # users' ownership column is "id", not "owner_id" -- confirms the
    # per-table column map, not a single hardcoded column name everywhere.
    is_valid, _, tables = SQLValidator.validate_sql(
        "SELECT id, name FROM users WHERE id = :owner_id",
        require_owner_scope=True,
    )
    assert is_valid is True
    assert "users" in tables

    # Reversed operand order (:owner_id = owner_id) must also be accepted.
    is_valid, _, _ = SQLValidator.validate_sql(
        "SELECT id FROM ingested_documents WHERE :owner_id = owner_id",
        require_owner_scope=True,
    )
    assert is_valid is True


def test_database_report_capability_registered_read_only_and_enforces_owner_scope(monkeypatch):
    """
    Phase 18: the new scheduled-report capability is registered, read-only
    (no approval gate -- it's a data-read, not a side effect), and threads
    enforce_owner_scope=True into DatabaseAgent.process_query so unscoped
    generated SQL falls back to the safe default query instead of running.
    """
    from app.execution.registry import task_registry
    from app.services import sql_generation_service as sql_gen_module

    meta = task_registry.get_metadata("database_report")
    assert meta.side_effect == "read_only"
    assert meta.requires_human_approval is False

    # Force the "generated" SQL to omit the owner-scoping predicate --
    # process_query must reject it (via SQLValidator) and fall back to the
    # hardcoded owner-scoped default rather than running the unscoped query.
    monkeypatch.setattr(
        sql_gen_module.sql_generation_service, "generate_sql",
        lambda question: ("SELECT source, chunk_count FROM ingested_documents", None),
    )

    db = SessionLocal()
    try:
        from app.agents.database_agent import database_agent
        res = database_agent.process_query(
            db=db, question="how many documents", owner_id="user_owner_scope_test",
            enforce_owner_scope=True,
        )
        assert "owner_id = :owner_id" in res.sql
    finally:
        db.close()


def test_database_query_service_execution():
    db = SessionLocal()
    try:
        # Ingest a sample doc first
        rag_pipeline.ingest(
            db=db,
            file_id="p4-db-doc-1",
            source="DB_Agent_Spec.pdf",
            owner_id="user_db_101",
            text="Project 4 Database Agent provides natural language query capabilities.",
        )

        # Execute read-only query
        sql = "SELECT file_id, source FROM ingested_documents WHERE owner_id = :owner_id"
        columns, rows, exec_time = database_query_service.execute_read_only_query(
            db=db,
            sql=sql,
            owner_id="user_db_101",
            limit=10,
        )

        assert "file_id" in columns
        assert "source" in columns
        assert len(rows) >= 1
        assert rows[0]["file_id"] == "p4-db-doc-1"
        assert exec_time >= 0.0
    finally:
        db.close()


def test_database_agent_nl_query_pipeline():
    db = SessionLocal()
    try:
        res = database_agent.process_query(
            db=db,
            question="How many documents have I uploaded?",
            owner_id="user_db_101",
            limit=5,
        )

        assert res.sql is not None
        assert isinstance(res.rows, list)
        assert res.explanation is not None
        assert len(res.explanation) > 0
    finally:
        db.close()
