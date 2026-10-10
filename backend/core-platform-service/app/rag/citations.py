from app.schemas.rag import CitationResult


class CitationsFormatter:

    @staticmethod
    def format_citations(candidates: list[dict]) -> list[CitationResult]:
        citations = []
        for item in candidates:
            citations.append(
                CitationResult(
                    chunk_id=str(item.get("chunk_id", "")),
                    file_id=str(item.get("file_id", "")),
                    source=str(item.get("source", "document.pdf")),
                    owner_id=str(item.get("owner_id", "1")),
                    page=int(item.get("page", 1)),
                    chunk_index=int(item.get("chunk_index", 0)),
                    text=str(item.get("text", "")),
                    score=float(item.get("score", 0.0)),
                    vector_score=float(item.get("vector_score", 0.0)),
                    keyword_score=float(item.get("keyword_score", 0.0)),
                    rerank_score=float(item.get("rerank_score", 0.0)),
                )
            )
        return citations


citations_formatter = CitationsFormatter()
