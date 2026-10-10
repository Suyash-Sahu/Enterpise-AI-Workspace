from unittest.mock import patch

import pytest
from app.db.database import SessionLocal, engine, Base
from app.execution.registry import task_registry
from app.execution.policies import execution_policy
from app.schemas.execution import ExecutionRequest, ExecutionStatus
from app.services.execution_manager import execution_manager
from app.rag.pipeline import rag_pipeline
from app.runtime.exceptions import RateLimitedError


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_task_registry_registration():
    tasks = task_registry.list_supported_tasks()
    assert "rag_search" in tasks
    assert "rag_answer" in tasks
    assert "database_query" in tasks
    assert "text_generation" in tasks
    assert "document_summary" in tasks


def test_policy_and_timeout():
    # 1. Mode validation
    assert execution_policy.validate_mode("AUTO") == "auto"
    assert execution_policy.validate_mode("local") == "local"
    assert execution_policy.validate_mode("cloud") == "cloud"
    with pytest.raises(ValueError):
        execution_policy.validate_mode("invalid_mode")

    # 2. Timeout resolution & capping
    assert execution_policy.resolve_timeout(None) == 30.0
    assert execution_policy.resolve_timeout(10.0) == 10.0
    assert execution_policy.resolve_timeout(500.0) == 120.0  # Capped at MAX_TIMEOUT


def test_idempotency_deduplication():
    db = SessionLocal()
    import uuid
    idem_key = f"test-idempotency-key-{uuid.uuid4().hex[:8]}"
    try:
        req = ExecutionRequest(
            task_type="rag_search",
            input={"query": "test idempotency query", "top_k": 3},
            idempotency_key=idem_key,
        )

        res1 = execution_manager.execute(db=db, request=req, owner_id="user_idempotency_1")
        assert res1.status == ExecutionStatus.COMPLETED
        assert res1.execution_id is not None

        # Repeat request with same idempotency key
        res2 = execution_manager.execute(db=db, request=req, owner_id="user_idempotency_1")
        assert res2.execution_id == res1.execution_id
        assert res2.idempotency_key == idem_key
    finally:
        db.close()


def test_rag_execution_pipeline():
    db = SessionLocal()
    try:
        # Ingest document first
        rag_pipeline.ingest(
            db=db,
            file_id="p5-exec-doc-1",
            source="P5_Execution_Spec.pdf",
            owner_id="user_exec_202",
            text="Project 5 Execution Manager handles task routing and lifecycle state tracking.",
        )

        req = ExecutionRequest(
            task_type="rag_answer",
            input={"question": "What does Project 5 Execution Manager handle?"},
            execution_mode="auto",
        )

        res = execution_manager.execute(db=db, request=req, owner_id="user_exec_202")
        assert res.status == ExecutionStatus.COMPLETED
        assert res.task_type == "rag_answer"
        assert res.result is not None
        assert "answer" in res.result
        assert res.execution_time >= 0.0
    finally:
        db.close()


def test_document_summary_file_id_path_does_not_crash_with_wrong_signature():
    """
    Regression (Phase 9 audit): DocumentSummaryHandler used to call
    rag_pipeline._fetch_from_google_connector(file_id) with only one
    positional argument, when the real signature is
    (db, user_id, file_id) -- always raising a bare TypeError before ever
    reaching Google, for every file_id-based summary request. Fixed to pass
    db/user_id correctly; failure now comes from the real "not connected"
    path (no Google account linked for this test owner), not a signature
    mismatch.
    """
    db = SessionLocal()
    try:
        req = ExecutionRequest(task_type="document_summary", input={"file_id": "some-file-id"})
        res = execution_manager.execute(db=db, request=req, owner_id="999999")
        assert res.status == ExecutionStatus.FAILED
        assert res.error_type != "TypeError", f"Signature bug regressed: {res.error_message}"
    finally:
        db.close()


def test_database_query_execution_pipeline():
    db = SessionLocal()
    try:
        req = ExecutionRequest(
            task_type="database_query",
            input={"question": "How many documents do I have?"},
            execution_mode="auto",
        )

        res = execution_manager.execute(db=db, request=req, owner_id="user_exec_202")
        assert res.status == ExecutionStatus.COMPLETED
        assert res.task_type == "database_query"
        assert res.result is not None
        assert "sql" in res.result
        assert "explanation" in res.result
    finally:
        db.close()


def test_tenant_isolation_and_history():
    db = SessionLocal()
    try:
        # User A executes task
        req_a = ExecutionRequest(task_type="text_generation", input={"prompt": "User A prompt"})
        res_a = execution_manager.execute(db=db, request=req_a, owner_id="user_tenant_A")

        # User B queries status of User A execution -> Access denied
        with pytest.raises(ValueError):
            execution_manager.get_status(db=db, execution_id=res_a.execution_id, owner_id="user_tenant_B")

        # User B history query -> does not contain User A records
        history_b = execution_manager.get_history(db=db, owner_id="user_tenant_B", limit=50)
        exec_ids_b = [item.execution_id for item in history_b.items]
        assert res_a.execution_id not in exec_ids_b
    finally:
        db.close()


def test_failed_cloud_attempt_is_recorded_as_cloud_not_auto():
    """
    Regression (2026-09-20 rate-limit investigation): a RateLimitedError is
    raised only by the cloud runtime's own HTTP dispatch (an HTTP 429 from a
    cloud provider -- see RateLimitedError's docstring), so it is
    unambiguous proof the attempt was a cloud one. Previously
    Execution.execution_mode kept its creation-time value ("auto", since the
    request's real placement is resolved deep inside the handler and only
    recorded on the success path) whenever the handler raised before
    returning -- so a genuinely-attempted-but-rate-limited cloud call was
    indistinguishable from "never routed anywhere", and
    app/evaluation/executor.py's `rec.execution_mode == "cloud"` check
    silently undercounted it. Now the failure path itself stamps "cloud"
    when the error is a RateLimitedError, independent of what the request's
    execution_mode happened to be at creation.
    """
    db = SessionLocal()
    try:
        handler = task_registry.get_handler("text_generation")
        with patch.object(handler, "execute", side_effect=RateLimitedError("rate limited", retry_after=None)):
            req = ExecutionRequest(
                task_type="text_generation",
                input={"prompt": "test prompt"},
                execution_mode="auto",
            )
            res = execution_manager.execute(db=db, request=req, owner_id="user_rate_limit_attribution")

        assert res.status == ExecutionStatus.FAILED
        assert res.error_type == "RateLimitedError"

        status = execution_manager.get_status(
            db=db, execution_id=res.execution_id, owner_id="user_rate_limit_attribution",
        )
        assert status.execution_mode == "cloud"
    finally:
        db.close()


def test_failed_local_attempt_still_reports_its_own_mode_not_cloud():
    """
    Guard against over-correcting the fix above: a non-RateLimitedError
    failure (e.g. a local Ollama connection error) must not be relabeled
    "cloud" -- only the unambiguous RateLimitedError signal should flip the
    recorded mode.
    """
    db = SessionLocal()
    try:
        handler = task_registry.get_handler("text_generation")
        with patch.object(handler, "execute", side_effect=RuntimeError("local provider unreachable")):
            req = ExecutionRequest(
                task_type="text_generation",
                input={"prompt": "test prompt"},
                execution_mode="local",
            )
            res = execution_manager.execute(db=db, request=req, owner_id="user_local_failure_attribution")

        assert res.status == ExecutionStatus.FAILED

        status = execution_manager.get_status(
            db=db, execution_id=res.execution_id, owner_id="user_local_failure_attribution",
        )
        assert status.execution_mode == "local"
    finally:
        db.close()
