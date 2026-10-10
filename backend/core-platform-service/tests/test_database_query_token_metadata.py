"""
Regression tests (Phase 10 token audit, 2026-09-20): database_query issues
TWO LLM calls (SQL generation, then result explanation), both previously
routed through ai_service.smart_generate() and both discarding the real
model/provider/runtime/token data -- DatabaseQueryHandler then hardcoded
provider="postgresql", model="nl-to-sql-v1" ("nl-to-sql-v1" was never a real
model name).

Fix: sql_generation_service.generate_sql() and
database_result_service.generate_explanation() now return
(text, Optional[RuntimeGenerateResponse]) tuples; database_agent.process_query()
aggregates both into DatabaseResult (tokens summed across both real calls,
model/provider/runtime attributed to the SQL-generation call, falling back
to the explanation call's); DatabaseQueryHandler reads the real values
instead of hardcoding.
"""
from unittest.mock import patch

from app.agents.database_agent import database_agent
from app.db.database import Base, engine
from app.db.session import SessionLocal
from app.execution.contracts import DatabaseQueryHandler, ExecutionContext
from app.schemas.runtime import RuntimeGenerateResponse


def _response(model: str, input_tokens: int, output_tokens: int) -> RuntimeGenerateResponse:
    return RuntimeGenerateResponse(
        completion="ignored by these mocks",
        provider="ollama",
        model=model,
        runtime="local",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
    )


def _patched_process_query(sql_response, explanation_response, row_count=2):
    """Mocks every collaborator of process_query() except the aggregation logic itself."""
    return (
        patch(
            "app.agents.database_agent.sql_generation_service.generate_sql",
            return_value=("SELECT 1", sql_response),
        ),
        patch(
            "app.agents.database_agent.SQLValidator.validate_sql",
            return_value=(True, "", {"ingested_documents"}),
        ),
        patch(
            "app.agents.database_agent.database_query_service.execute_read_only_query",
            return_value=(["col"], [{"col": "v"}] * row_count, 0.01),
        ),
        patch(
            "app.agents.database_agent.database_result_service.generate_explanation",
            return_value=("Explanation text.", explanation_response),
        ),
    )


def test_database_query_sums_tokens_across_both_llm_calls():
    sql_resp = _response("qwen2.5:3b-instruct", input_tokens=30, output_tokens=10)
    explain_resp = _response("qwen2.5:3b-instruct", input_tokens=20, output_tokens=5)

    patches = _patched_process_query(sql_resp, explain_resp)
    with patches[0], patches[1], patches[2], patches[3]:
        db = SessionLocal()
        try:
            res = database_agent.process_query(db=db, question="How many users?", owner_id="1")
        finally:
            db.close()

    assert res.model == "qwen2.5:3b-instruct"
    assert res.provider == "ollama"
    assert res.runtime == "local"
    # 30+20 input, 10+5 output -- both real LLM calls' spend counted, not just one.
    assert res.input_tokens == 50
    assert res.output_tokens == 15
    assert res.total_tokens == 65


def test_database_query_attributes_metadata_to_sql_generation_when_explanation_fails():
    sql_resp = _response("qwen2.5:3b-instruct", input_tokens=30, output_tokens=10)

    patches = _patched_process_query(sql_resp, explanation_response=None)
    with patches[0], patches[1], patches[2], patches[3]:
        db = SessionLocal()
        try:
            res = database_agent.process_query(db=db, question="How many users?", owner_id="1")
        finally:
            db.close()

    assert res.model == "qwen2.5:3b-instruct"
    assert res.input_tokens == 30
    assert res.output_tokens == 10
    assert res.total_tokens == 40


def test_database_query_metadata_none_when_both_llm_calls_failed():
    patches = _patched_process_query(sql_response=None, explanation_response=None)
    with patches[0], patches[1], patches[2], patches[3]:
        db = SessionLocal()
        try:
            res = database_agent.process_query(db=db, question="How many users?", owner_id="1")
        finally:
            db.close()

    assert res.model is None
    assert res.provider is None
    assert res.runtime is None
    assert res.input_tokens is None
    assert res.output_tokens is None
    assert res.total_tokens is None


def test_database_query_handler_surfaces_real_metadata_not_hardcoded():
    """
    DatabaseQueryHandler previously always returned provider="postgresql",
    model="nl-to-sql-v1" ("nl-to-sql-v1" was never a real model). It must now
    surface the real model/provider/runtime and a "tokens" key when a real
    LLM response is available.
    """
    sql_resp = _response("qwen2.5:3b-instruct", input_tokens=30, output_tokens=10)
    patches = _patched_process_query(sql_resp, explanation_response=None)

    Base.metadata.create_all(bind=engine)
    with patches[0], patches[1], patches[2], patches[3]:
        db = SessionLocal()
        try:
            handler_result = DatabaseQueryHandler().execute(
                db=db,
                context=ExecutionContext(owner_id="1", execution_id="exec_1"),
                input_data={"question": "How many users?"},
            )
        finally:
            db.close()

    assert handler_result["provider"] == "ollama"
    assert handler_result["model"] == "qwen2.5:3b-instruct"
    assert handler_result["runtime"] == "local"
    assert handler_result["tokens"] == {"input": 30, "output": 10, "total": 40}


def test_database_query_handler_falls_back_to_postgresql_label_when_no_llm_metadata():
    """
    Unlike rag_answer (no legitimate non-LLM fallback), a database_query
    where both LLM calls failed still genuinely executed a real DB read --
    "postgresql" remains a truthful fallback label here, not a fabricated one.
    """
    patches = _patched_process_query(sql_response=None, explanation_response=None)

    Base.metadata.create_all(bind=engine)
    with patches[0], patches[1], patches[2], patches[3]:
        db = SessionLocal()
        try:
            handler_result = DatabaseQueryHandler().execute(
                db=db,
                context=ExecutionContext(owner_id="1", execution_id="exec_1"),
                input_data={"question": "How many users?"},
            )
        finally:
            db.close()

    assert handler_result["provider"] == "postgresql"
    assert handler_result["model"] == "nl-to-sql-v1"
    assert "tokens" not in handler_result
