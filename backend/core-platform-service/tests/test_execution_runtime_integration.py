import pytest

from app.core.config import settings
from app.db.database import SessionLocal, engine, Base
from app.schemas.execution import ExecutionRequest, ExecutionStatus
from app.services.execution_manager import execution_manager


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_p5_to_p6_text_generation_local():
    db = SessionLocal()
    try:
        req = ExecutionRequest(
            task_type="text_generation",
            input={"prompt": "Explain vector search in one sentence."},
            execution_mode="local",
            request_id="trace_req_p5_p6_local_101",
        )

        res = execution_manager.execute(db=db, request=req, owner_id="user_p5_p6_integration")
        assert res.task_type == "text_generation"
        assert res.request_id == "trace_req_p5_p6_local_101"

        if res.status == ExecutionStatus.COMPLETED:
            assert res.result is not None
            assert "generated_text" in res.result
            assert res.provider == "ollama"
        else:
            # Proof of Local Privacy Boundary: Ollama offline raises ProviderUnavailableError without cloud leak
            assert res.status == ExecutionStatus.FAILED
            assert res.error_type == "ProviderUnavailableError"
    finally:
        db.close()


@pytest.mark.skipif(
    not settings.RUNTIME_CLOUD_ENABLED,
    reason="live cloud round-trip; development runs Ollama-only "
           "(set RUNTIME_CLOUD_ENABLED=true and OPENROUTER_API_KEY to run)",
)
def test_p5_to_p6_text_generation_cloud():
    db = SessionLocal()
    try:
        req = ExecutionRequest(
            task_type="text_generation",
            input={"prompt": "Explain hybrid search in one sentence."},
            execution_mode="cloud",
            request_id="trace_req_p5_p6_cloud_202",
        )

        res = execution_manager.execute(db=db, request=req, owner_id="user_p5_p6_integration")
        assert res.status == ExecutionStatus.COMPLETED
        assert res.task_type == "text_generation"
        assert res.request_id == "trace_req_p5_p6_cloud_202"
        assert res.result is not None
        assert "generated_text" in res.result
    finally:
        db.close()


@pytest.mark.skipif(
    not settings.RUNTIME_CLOUD_ENABLED,
    reason="live cloud round-trip; development runs Ollama-only "
           "(set RUNTIME_CLOUD_ENABLED=true and OPENROUTER_API_KEY to run)",
)
def test_p5_to_p6_document_summary():
    db = SessionLocal()
    try:
        req = ExecutionRequest(
            task_type="document_summary",
            # Deliberately unambiguous public content. The previous fixture
            # described this product's own internal architecture and the privacy
            # classifier now labels it 'internal' (confidence 0.82), which
            # correctly refuses cloud placement. The point of this test is the
            # P5 -> P6 document-summary path over cloud, so the fixture uses
            # textbook material instead; refusal of sensitive content on an
            # explicit cloud request is covered in test_privacy_routing.py.
            input={
                "text": "The CAP theorem states that a distributed data store "
                "cannot simultaneously guarantee consistency, availability and "
                "partition tolerance."
            },
            execution_mode="cloud",
        )

        res = execution_manager.execute(db=db, request=req, owner_id="user_p5_p6_integration")
        assert res.status == ExecutionStatus.COMPLETED
        assert res.task_type == "document_summary"
        assert res.result is not None
        assert "summary" in res.result
    finally:
        db.close()
