import logging
from sqlalchemy.orm import Session

from app.core.trust_boundary import ContentBlock, ContentSource, render_for_prompt
from app.models.document_chunk import IngestedDocument, DocumentChunk
from app.processors.document_processor import DocumentProcessor
from app.rag.chunking import Chunker
from app.rag.embeddings import embedding_service
from app.rag.hybrid_search import hybrid_search_service
from app.services.google_connector_service import GoogleConnectorService
from app.services.ai_service import ai_service
from app.schemas.rag import (
    IngestResponse,
    CitationResult,
    AnswerResponse,
    IngestedDocumentInfo,
)

logger = logging.getLogger(__name__)


class RAGPipeline:

    @staticmethod
    def _fetch_from_google_connector(db: Session, user_id: int, file_id: str) -> str:
        details = GoogleConnectorService.drive_file_details(db, user_id, file_id)
        name = details.get("name", file_id)
        mime_type = details.get("mimeType", "")

        if mime_type.startswith("application/vnd.google-apps."):
            content = GoogleConnectorService.export_google_doc(db, user_id, file_id)
        else:
            raw = GoogleConnectorService.download_drive_file(db, user_id, file_id)
            content = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw

        return f"Document Title: {name}\n\nContent:\n{content}"

    @staticmethod
    def ingest(
        db: Session,
        file_id: str,
        source: str = "Enterprise_AI_Workspace_PRD.pdf",
        owner_id: str = "1",
        text: str | None = None,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> IngestResponse:
        if not text:
            try:
                user_id = int(owner_id)
            except (TypeError, ValueError):
                raise ValueError(
                    f"owner_id {owner_id!r} is not a users.id, so file {file_id!r} "
                    "cannot be fetched from that user's Google Drive without explicit text."
                ) from None
            raw_text = RAGPipeline._fetch_from_google_connector(db, user_id, file_id)
        else:
            raw_text = text

        cleaned_text = DocumentProcessor.clean_text(raw_text)
        if not cleaned_text:
            cleaned_text = f"Empty document content for file ID {file_id}."

        chunk_list = Chunker.chunk_document(
            text=cleaned_text,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        texts = [c.text for c in chunk_list]
        embeddings = embedding_service.generate_embeddings_batch(texts)

        # Upsert: delete existing ingested document record & chunks for (owner_id, file_id)
        existing_doc = (
            db.query(IngestedDocument)
            .filter(IngestedDocument.owner_id == owner_id, IngestedDocument.file_id == file_id)
            .first()
        )
        if existing_doc:
            db.delete(existing_doc)
            db.commit()

        # Insert new IngestedDocument parent record
        ingested_doc = IngestedDocument(
            file_id=file_id,
            source=source,
            owner_id=owner_id,
            chunk_count=len(chunk_list),
        )
        db.add(ingested_doc)
        db.commit()
        db.refresh(ingested_doc)

        # Insert child DocumentChunk records referencing document_id (FK)
        meta = DocumentProcessor.extract_metadata(cleaned_text, source)
        db_chunks = []
        for i, chunk_data in enumerate(chunk_list):
            db_chunk = DocumentChunk(
                document_id=ingested_doc.id,
                owner_id=owner_id,
                file_id=file_id,
                source=source,
                chunk_index=chunk_data.chunk_index,
                text=chunk_data.text,
                page=chunk_data.page,
            )
            db_chunk.set_metadata({
                "word_count": chunk_data.word_count,
                "start_char": chunk_data.start_char,
                "end_char": chunk_data.end_char,
                "document_extension": meta.get("extension", "txt"),
            })
            db_chunk.set_vector(embeddings[i])
            db_chunks.append(db_chunk)

        db.add_all(db_chunks)
        db.commit()

        return IngestResponse(
            file_id=file_id,
            source=source,
            owner_id=owner_id,
            chunks_created=len(db_chunks),
            total_characters=len(cleaned_text),
            status="INGESTED",
        )

    @staticmethod
    def search(
        db: Session,
        query: str,
        top_k: int = 5,
        file_id: str | None = None,
        owner_id: str = "1",
        alpha: float = 0.5,
    ) -> list[CitationResult]:
        return hybrid_search_service.search(
            db=db,
            query_str=query,
            top_k=top_k,
            file_id=file_id,
            owner_id=owner_id,
            alpha=alpha,
        )

    @staticmethod
    def answer(
        db: Session,
        question: str,
        top_k: int = 5,
        file_id: str | None = None,
        owner_id: str = "1",
    ) -> AnswerResponse:
        citations = hybrid_search_service.search(
            db=db,
            query_str=question,
            top_k=top_k,
            file_id=file_id,
            owner_id=owner_id,
        )

        if not citations:
            return AnswerResponse(
                question=question,
                answer="No relevant document context found in the workspace index to answer your question.",
                citations_count=0,
                citations=[],
            )

        # Retrieved citations are untrusted content -- each is wrapped in
        # <untrusted_data> delimiters (app/core/trust_boundary.py) so an
        # adversarial document chunk cannot pass its content off as
        # instructions to the model.
        citation_blocks = [
            ContentBlock(
                content=f"[Source {idx+1}: {cit.source} (Page {cit.page})]\n{cit.text}",
                source=ContentSource.RETRIEVED_CONTENT,
                label=f"citation_{idx+1}",
            )
            for idx, cit in enumerate(citations)
        ]

        prompt = render_for_prompt([
            ContentBlock(
                content=(
                    "You are the Enterprise AI Document RAG Assistant. Answer "
                    "the user question accurately based ONLY on the provided "
                    "document citations below."
                ),
                source=ContentSource.SYSTEM,
            ),
            *citation_blocks,
            ContentBlock(content=f"USER QUESTION: {question}", source=ContentSource.USER),
            ContentBlock(
                content="Provide a clear, direct, and grounded answer citing sources where relevant.",
                source=ContentSource.SYSTEM,
            ),
        ])

        # generate_with_metadata() instead of smart_generate(): same call,
        # but returns the real model/provider/runtime/token counts instead
        # of discarding them (Phase 10 token audit, 2026-09-20). Replicates
        # smart_generate()'s own success/failure semantics exactly (empty or
        # failed completion -> AIService.DEFAULT_FALLBACK) so the answer text
        # returned to callers is unchanged either way.
        response = None
        try:
            response = ai_service.generate_with_metadata(prompt=prompt)
            answer_text = (
                response.completion
                if response and response.completion and response.completion.strip()
                else ai_service.DEFAULT_FALLBACK
            )
        except Exception:
            answer_text = ai_service.DEFAULT_FALLBACK

        got_real_completion = bool(
            response and response.completion and response.completion.strip()
        )

        return AnswerResponse(
            question=question,
            answer=answer_text,
            citations_count=len(citations),
            citations=citations,
            model=response.model if got_real_completion else None,
            provider=response.provider if got_real_completion else None,
            runtime=response.runtime if got_real_completion else None,
            input_tokens=response.input_tokens if got_real_completion else None,
            output_tokens=response.output_tokens if got_real_completion else None,
            total_tokens=response.total_tokens if got_real_completion else None,
        )

    @staticmethod
    def list_documents(db: Session, owner_id: str = "1") -> list[IngestedDocumentInfo]:
        docs = (
            db.query(IngestedDocument)
            .filter(IngestedDocument.owner_id == owner_id)
            .order_by(IngestedDocument.id.desc())
            .all()
        )
        return [
            IngestedDocumentInfo(
                id=d.id,
                file_id=d.file_id,
                source=d.source,
                owner_id=d.owner_id,
                chunk_count=d.chunk_count,
                ingested_at=d.ingested_at.isoformat() if d.ingested_at else "",
            )
            for d in docs
        ]

    @staticmethod
    def delete_document(db: Session, file_id: str, owner_id: str = "1") -> bool:
        doc = (
            db.query(IngestedDocument)
            .filter(IngestedDocument.owner_id == owner_id, IngestedDocument.file_id == file_id)
            .first()
        )
        if doc:
            db.delete(doc)
            db.commit()
            return True
        return False


rag_pipeline = RAGPipeline()
