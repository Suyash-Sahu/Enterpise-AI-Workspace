import pytest
from app.db.database import SessionLocal, engine, Base
from app.connectors.google.exceptions import GoogleNotConnectedError
from app.rag.chunking import Chunker
from app.rag.pipeline import rag_pipeline


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_sentence_boundary_chunking():
    text = "Sentence 1 is part of AMOF architecture. Sentence 2 describes vector similarity search."
    chunks = Chunker.chunk_document(text, chunk_size=500)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0


def test_document_ingestion_and_relational_cascade():
    db = SessionLocal()
    try:
        file_id = "test-doc-rag-2026"
        source = "Architecture_Spec.pdf"
        owner_id = "user_101"
        text = (
            "Enterprise AI Workspace PRD Specification.\n"
            "Section 1: Multi-Agent Intent Classifier.\n"
            "Section 2: RAG Vector Indexing and Hybrid Search.\n"
            "Section 3: OAuth 2.0 Security and Audit Logs."
        )

        res = rag_pipeline.ingest(
            db=db,
            file_id=file_id,
            source=source,
            owner_id=owner_id,
            text=text,
            chunk_size=150,
            chunk_overlap=30,
        )

        assert res.file_id == file_id
        assert res.chunks_created > 0
        assert res.status == "INGESTED"

        # Verify listing
        docs = rag_pipeline.list_documents(db=db, owner_id=owner_id)
        assert any(d.file_id == file_id for d in docs)

        # Cleanup via cascade delete
        deleted = rag_pipeline.delete_document(db=db, file_id=file_id, owner_id=owner_id)
        assert deleted is True
    finally:
        db.close()


def test_ingest_without_text_fails_instead_of_fabricating_content():
    """
    Regression: ingest() used to silently fall back to a hardcoded PRD blurb
    whenever the Drive fetch failed, so every no-text ingest looked like a
    success while indexing fake content. It must now surface the real failure.
    """
    db = SessionLocal()
    try:
        with pytest.raises(GoogleNotConnectedError):
            rag_pipeline.ingest(db=db, file_id="no-google-grant-doc", owner_id="999999")
    finally:
        db.close()


def test_multi_tenant_owner_id_isolation():
    db = SessionLocal()
    try:
        user1_file = "user1-doc"
        user2_file = "user2-doc"

        rag_pipeline.ingest(db=db, file_id=user1_file, source="User1.pdf", owner_id="user_1", text="User 1 confidential data on vector index.")
        rag_pipeline.ingest(db=db, file_id=user2_file, source="User2.pdf", owner_id="user_2", text="User 2 secret financial statement.")

        # Search as user_1
        user1_results = rag_pipeline.search(db=db, query="secret financial statement", owner_id="user_1")
        # Should NOT return User 2's document
        for cit in user1_results:
            assert cit.owner_id == "user_1"
            assert cit.file_id != user2_file

        # Cleanup
        rag_pipeline.delete_document(db=db, file_id=user1_file, owner_id="user_1")
        rag_pipeline.delete_document(db=db, file_id=user2_file, owner_id="user_2")
    finally:
        db.close()
