import re
import math
import logging
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.document_chunk import DocumentChunk
from app.rag.embeddings import embedding_service
from app.rag.reranker import reranker_service
from app.rag.citations import citations_formatter
from app.schemas.rag import CitationResult

logger = logging.getLogger(__name__)


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 > 0 and norm2 > 0:
        return dot / (norm1 * norm2)
    return 0.0


class HybridSearchService:

    @staticmethod
    def vector_search(
        db: Session,
        query_vector: list[float],
        top_k: int = 20,
        file_id: str | None = None,
        owner_id: str = "1",
    ) -> list[dict]:
        query = db.query(DocumentChunk).filter(DocumentChunk.owner_id == owner_id)
        if file_id:
            query = query.filter(DocumentChunk.file_id == file_id)

        chunks = query.all()
        if not chunks:
            return []

        results = []
        for chunk in chunks:
            vec = chunk.get_vector()
            sim = cosine_similarity(query_vector, vec)
            results.append({
                "chunk": chunk,
                "vector_score": round(max(0.0, min(1.0, sim)), 4),
            })

        results.sort(key=lambda x: x["vector_score"], reverse=True)
        return results[:top_k]

    @staticmethod
    def keyword_search(
        db: Session,
        query_str: str,
        top_k: int = 20,
        file_id: str | None = None,
        owner_id: str = "1",
    ) -> list[dict]:
        query = db.query(DocumentChunk).filter(DocumentChunk.owner_id == owner_id)
        if file_id:
            query = query.filter(DocumentChunk.file_id == file_id)

        chunks = query.all()
        if not chunks:
            return []

        q_words = [w.lower() for w in re.findall(r"\w+", query_str)]
        if not q_words:
            return []

        results = []
        for chunk in chunks:
            text_lower = chunk.text.lower()
            chunk_words = re.findall(r"\w+", text_lower)
            if not chunk_words:
                continue

            matches = sum(chunk_words.count(w) for w in set(q_words))
            unique_matches = sum(1 for w in set(q_words) if w in text_lower)

            tf = matches / float(len(chunk_words))
            coverage = unique_matches / float(len(set(q_words)))

            kw_score = min(1.0, (coverage * 0.7) + (tf * 0.3 * 5.0))
            if kw_score > 0:
                results.append({
                    "chunk": chunk,
                    "keyword_score": round(kw_score, 4),
                })

        results.sort(key=lambda x: x["keyword_score"], reverse=True)
        return results[:top_k]

    @staticmethod
    def search(
        db: Session,
        query_str: str,
        top_k: int = 5,
        file_id: str | None = None,
        owner_id: str = "1",
        alpha: float = 0.5,
    ) -> list[CitationResult]:
        query_vector = embedding_service.generate_embedding(query_str)

        candidate_limit = max(20, top_k * 3)
        vec_results = HybridSearchService.vector_search(db, query_vector, candidate_limit, file_id, owner_id)
        kw_results = HybridSearchService.keyword_search(db, query_str, candidate_limit, file_id, owner_id)

        rrf_k = settings.RRF_K
        chunk_map: dict[str, dict] = {}

        for rank_idx, item in enumerate(vec_results):
            c: DocumentChunk = item["chunk"]
            cid = c.id
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "chunk": c,
                    "vector_score": item["vector_score"],
                    "keyword_score": 0.0,
                    "vec_rank": rank_idx + 1,
                    "kw_rank": 999,
                }
            else:
                chunk_map[cid]["vector_score"] = item["vector_score"]
                chunk_map[cid]["vec_rank"] = rank_idx + 1

        for rank_idx, item in enumerate(kw_results):
            c: DocumentChunk = item["chunk"]
            cid = c.id
            if cid not in chunk_map:
                chunk_map[cid] = {
                    "chunk": c,
                    "vector_score": 0.0,
                    "keyword_score": item["keyword_score"],
                    "vec_rank": 999,
                    "kw_rank": rank_idx + 1,
                }
            else:
                chunk_map[cid]["keyword_score"] = item["keyword_score"]
                chunk_map[cid]["kw_rank"] = rank_idx + 1

        candidates = []
        for cid, data in chunk_map.items():
            chunk: DocumentChunk = data["chunk"]
            vec_rank = data["vec_rank"]
            kw_rank = data["kw_rank"]

            rrf_score = (1.0 / (rrf_k + vec_rank)) + (1.0 / (rrf_k + kw_rank))
            weighted_score = (alpha * data["vector_score"]) + ((1.0 - alpha) * data["keyword_score"]) + (rrf_score * 5.0)
            norm_score = round(max(0.01, min(0.99, weighted_score)), 4)

            candidates.append({
                "chunk_id": chunk.id,
                "file_id": chunk.file_id,
                "source": chunk.source,
                "owner_id": chunk.owner_id,
                "page": chunk.page or 1,
                "chunk_index": chunk.chunk_index,
                "text": chunk.text,
                "score": norm_score,
                "vector_score": data["vector_score"],
                "keyword_score": data["keyword_score"],
                "rerank_score": norm_score,
            })

        reranked_results = reranker_service.rerank(query_str, candidates, top_k)
        return citations_formatter.format_citations(reranked_results)


hybrid_search_service = HybridSearchService()
