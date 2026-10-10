"""
Regression tests (Phase 10 token audit, 2026-09-20): rag_pipeline.answer()
previously called ai_service.smart_generate(), which returns only the
completion string -- the real model/provider/runtime/token counts computed
internally by runtime_service.generate() were discarded before they ever
reached AnswerResponse or RAGAnswerHandler, which then hardcoded
provider="openai/openrouter", model="gpt-4o-mini" regardless of what
actually ran (including when it was Ollama local).

Fix: ai_service.generate_with_metadata() returns the full
RuntimeGenerateResponse; rag_pipeline.answer() now uses it and attaches the
real values to AnswerResponse (None when the canned fallback was used
instead of a real completion), and RAGAnswerHandler reads them off directly
instead of hardcoding.
"""
from unittest.mock import patch

from app.db.database import Base, engine
from app.db.session import SessionLocal
from app.execution.contracts import ExecutionContext, RAGAnswerHandler
from app.rag.pipeline import rag_pipeline
from app.schemas.rag import CitationResult
from app.schemas.runtime import RuntimeGenerateResponse
from app.services.ai_service import ai_service


def _fake_citation() -> CitationResult:
    return CitationResult(
        chunk_id="chunk_1",
        file_id="file_1",
        source="Doc.pdf",
        owner_id="1",
        page=1,
        chunk_index=0,
        text="Relevant chunk text.",
        score=0.9,
        vector_score=0.9,
        keyword_score=0.5,
        rerank_score=0.9,
    )


def _fake_response(**overrides) -> RuntimeGenerateResponse:
    base = dict(
        completion="A grounded answer.",
        provider="ollama",
        model="qwen2.5:3b-instruct",
        runtime="local",
        input_tokens=42,
        output_tokens=17,
        total_tokens=59,
    )
    base.update(overrides)
    return RuntimeGenerateResponse(**base)


def test_rag_answer_propagates_real_model_provider_runtime_tokens():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        with patch(
            "app.rag.pipeline.hybrid_search_service.search",
            return_value=[_fake_citation()],
        ), patch.object(
            ai_service, "generate_with_metadata", return_value=_fake_response()
        ):
            res = rag_pipeline.answer(db=db, question="What is the policy?", owner_id="1")

        assert res.answer == "A grounded answer."
        assert res.model == "qwen2.5:3b-instruct"
        assert res.provider == "ollama"
        assert res.runtime == "local"
        assert res.input_tokens == 42
        assert res.output_tokens == 17
        assert res.total_tokens == 59
    finally:
        db.close()


def test_rag_answer_falls_back_with_none_metadata_on_generation_failure():
    """
    Preserves smart_generate()'s exact failure behavior (the generic
    DEFAULT_FALLBACK text) while metadata is None rather than a fabricated
    model/provider -- never claim a real model ran when it didn't.
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        with patch(
            "app.rag.pipeline.hybrid_search_service.search",
            return_value=[_fake_citation()],
        ), patch.object(
            ai_service, "generate_with_metadata", side_effect=RuntimeError("provider unavailable")
        ):
            res = rag_pipeline.answer(db=db, question="What is the policy?", owner_id="1")

        assert res.answer == ai_service.DEFAULT_FALLBACK
        assert res.model is None
        assert res.provider is None
        assert res.runtime is None
        assert res.input_tokens is None
        assert res.output_tokens is None
        assert res.total_tokens is None
    finally:
        db.close()


def test_rag_answer_handler_surfaces_real_metadata_not_hardcoded():
    """
    RAGAnswerHandler previously always returned provider="openai/openrouter",
    model="gpt-4o-mini" no matter what actually ran. It must now surface the
    real values (and a "tokens" key execution/executor.py can persist).
    """
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        with patch(
            "app.rag.pipeline.hybrid_search_service.search",
            return_value=[_fake_citation()],
        ), patch.object(
            ai_service, "generate_with_metadata", return_value=_fake_response()
        ):
            handler_result = RAGAnswerHandler().execute(
                db=db,
                context=ExecutionContext(owner_id="1", execution_id="exec_1"),
                input_data={"question": "What is the policy?"},
            )

        assert handler_result["provider"] == "ollama"
        assert handler_result["model"] == "qwen2.5:3b-instruct"
        assert handler_result["runtime"] == "local"
        assert handler_result["tokens"] == {"input": 42, "output": 17, "total": 59}
    finally:
        db.close()
