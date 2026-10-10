import re
import logging

logger = logging.getLogger(__name__)


class RerankerService:

    @staticmethod
    def _compute_relevance_score(query: str, chunk_text: str, base_score: float) -> float:
        if not query or not chunk_text:
            return 0.0

        q_terms = set(re.findall(r"\w+", query.lower()))
        if not q_terms:
            return base_score

        chunk_words = re.findall(r"\w+", chunk_text.lower())
        c_set = set(chunk_words)

        phrase_bonus = 0.0
        if query.lower().strip() in chunk_text.lower():
            phrase_bonus = 0.35

        matched_terms = q_terms.intersection(c_set)
        overlap_ratio = len(matched_terms) / float(len(q_terms))

        term_freq = sum(chunk_words.count(t) for t in matched_terms)
        density_score = min(1.0, term_freq / float(max(10, len(chunk_words))))

        final_score = (
            base_score * 0.40 +
            overlap_ratio * 0.35 +
            phrase_bonus +
            density_score * 0.15
        )

        return max(0.01, min(0.99, round(final_score, 4)))

    def rerank(
        self,
        query: str,
        candidates: list[dict],
        top_k: int = 5,
    ) -> list[dict]:
        if not candidates:
            return []

        reranked = []
        for item in candidates:
            orig_score = item.get("score", 0.5)
            chunk_text = item.get("text", "")

            r_score = self._compute_relevance_score(query, chunk_text, orig_score)

            item_copy = dict(item)
            item_copy["rerank_score"] = r_score
            item_copy["score"] = round(r_score * 0.7 + orig_score * 0.3, 4)
            reranked.append(item_copy)

        reranked.sort(key=lambda x: x["score"], reverse=True)
        return reranked[:top_k]


reranker_service = RerankerService()
