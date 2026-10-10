import pytest

from app.core.config import settings
from app.db.database import SessionLocal, engine, Base
from app.schemas.supervisor import SupervisorRequest
from app.services.supervisor_service import supervisor_service


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_supervisor_database_query_integration():
    db = SessionLocal()
    try:
        req = SupervisorRequest(
            question="How many documents do I have indexed?",
            execution_mode="auto",
        )
        res = supervisor_service.execute(db=db, request=req, owner_id="user_p7_test_owner")
        assert res.status in ("COMPLETED", "FAILED")
        assert res.intent.capability == "database_query"
        assert res.request_id is not None
        assert res.trace_id is not None
        assert len(res.execution_ids) >= 1
    finally:
        db.close()


def test_supervisor_rag_answer_integration():
    db = SessionLocal()
    try:
        req = SupervisorRequest(
            question="How does hybrid search work in my documents?",
            execution_mode="auto",
        )
        res = supervisor_service.execute(db=db, request=req, owner_id="user_p7_test_owner")
        assert res.status in ("COMPLETED", "FAILED")
        assert res.intent.capability == "rag_answer"
        assert res.request_id is not None
        assert res.trace_id is not None
    finally:
        db.close()


@pytest.mark.skipif(
    not settings.RUNTIME_CLOUD_ENABLED,
    reason="live cloud round-trip; development runs Ollama-only "
           "(set RUNTIME_CLOUD_ENABLED=true and OPENROUTER_API_KEY to run)",
)
def test_supervisor_text_generation_integration():
    db = SessionLocal()
    try:
        req = SupervisorRequest(
            # Unambiguously public subject matter. "Write an overview of the
            # AMOF framework" fail-closed to confidential: no exemplar covers
            # this project's own domain vocabulary, so stage 2 could not clear
            # it and an explicit cloud request is correctly refused. That is the
            # measured over-restriction cost, not a defect — the fix is broader
            # exemplar coverage, not a weaker constraint.
            question="Write a concise overview of how HTTP caching headers work.",
            execution_mode="cloud",
        )
        res = supervisor_service.execute(db=db, request=req, owner_id="user_p7_test_owner")
        assert res.status == "COMPLETED"
        assert res.intent.capability == "text_generation"
        assert len(res.answer) > 0
        assert len(res.execution_ids) >= 1
    finally:
        db.close()


def test_supervisor_health_service():
    health = supervisor_service.health()
    assert health.status == "online"
    assert health.supervisor_enabled is True
    assert health.p5_available is True
    assert "database_query" in health.supported_capabilities
