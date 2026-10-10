"""
LLM-as-judge answer quality scoring, for the evaluation harness only.

This is deliberately separate from app/supervisor/verifier.py. The verifier's
own docstring is explicit that its checks are "mechanical" and "do not attempt
to judge whether an answer is correct" -- non-degeneracy, grounding word
overlap, row-count consistency. Those are real, cheap, and honest, but they
cannot tell a fluent, well-organised, correct answer from an awkward one that
happens to share vocabulary with the retrieved passages. This module is the
thing that actually judges.

Replaces the previous output_quality_score wiring, which set it to
verification.confidence -- a mean of the mechanical checks. That was already
an improvement over Week 1's original hardcoded 0.95 constant, but it is still
a hand-designed formula, not a quality judgment, and conflating "structurally
supported" with "good" made both signals less legible. They are kept apart
now: verification.* stays mechanical; output_quality_score comes from here.

Rubric: faithfulness / relevance / completeness, 0.0-1.0 each, averaged.
Mirrors RAGAS-style LLM-judge evaluation methodology rather than inventing a
bespoke one.

Local model only, same policy as app/privacy/classifier.py's stage-3 judge and
for the same reason: the question and answer being judged here are real
production content from an evaluation run, potentially sensitive, and judging
them is not a reason to send them anywhere the router would not otherwise
send them. Calls ollama_runtime directly rather than through
runtime_service/privacy_router -- this is a judge call, not a routing
decision, so it has no business going through the privacy-constrained router
at all (nothing here is choosing a placement).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

_JUDGE_PROMPT = """You are grading the quality of an AI assistant's answer to a user's question, for an evaluation benchmark. Score three dimensions, each from 0.0 (fails) to 1.0 (excellent):

- "faithfulness": Is the answer consistent with the provided context (if any) and not contradicted by it? An answer that invents specifics not supported by the context, or that contradicts it, scores low. If no context is given, judge faithfulness as whether the answer avoids confidently-stated claims that would need a source.
- "relevance": Does the answer actually address what was asked, rather than a related-but-different question?
- "completeness": Does the answer cover what the question needed, without leaving out a clearly necessary part?

Respond with JSON only, no other text: {{"faithfulness": <0.0-1.0>, "relevance": <0.0-1.0>, "completeness": <0.0-1.0>, "rationale": "<one short sentence>"}}

Question:
{question}

Context provided to the assistant (may be empty):
{context}

Assistant's answer:
{answer}
"""


@dataclass
class QualityJudgment:
    faithfulness: Optional[float] = None
    relevance: Optional[float] = None
    completeness: Optional[float] = None
    rationale: str = ""
    judged: bool = False
    latency_ms: float = 0.0

    @property
    def overall(self) -> Optional[float]:
        scores = [s for s in (self.faithfulness, self.relevance, self.completeness) if s is not None]
        if not scores:
            return None
        return sum(scores) / len(scores)

    def to_dict(self) -> dict[str, Any]:
        return {
            "faithfulness": self.faithfulness,
            "relevance": self.relevance,
            "completeness": self.completeness,
            "overall": self.overall,
            "rationale": self.rationale,
            "judged": self.judged,
            "latency_ms": round(self.latency_ms, 2),
        }


class QualityJudge:

    def judge(
        self,
        question: str,
        answer: str,
        context_snippets: Optional[list[str]] = None,
    ) -> QualityJudgment:
        """
        Grades one (question, answer) pair. Returns judged=False (all scores
        None) when the judge is disabled or the local runtime is unreachable
        -- callers must treat that as "not measured", never as a zero score.
        A missing measurement and a bad answer are different facts; scoring
        an unreachable judge as 0.0 would silently punish every run made
        while Ollama happens to be down.
        """
        started = time.time()

        if not settings.QUALITY_JUDGE_ENABLED:
            return QualityJudgment(judged=False, rationale="Quality judge disabled.")

        if not (answer or "").strip():
            return QualityJudgment(
                faithfulness=0.0, relevance=0.0, completeness=0.0,
                rationale="Empty answer.", judged=True,
                latency_ms=round((time.time() - started) * 1000, 2),
            )

        from app.runtime.local_runtime import ollama_runtime
        from app.schemas.runtime import RuntimeGenerateRequest, RuntimeMode

        context = "\n---\n".join(context_snippets or [])[: settings.QUALITY_JUDGE_MAX_CONTEXT_CHARS]
        prompt = _JUDGE_PROMPT.format(
            question=(question or "")[:2000],
            context=context or "(none provided)",
            answer=answer[:4000],
        )

        try:
            res = ollama_runtime.generate(
                RuntimeGenerateRequest(
                    prompt=prompt,
                    execution_mode=RuntimeMode.LOCAL,
                    model=settings.QUALITY_JUDGE_MODEL or None,
                    temperature=0.0,
                    max_tokens=200,
                    timeout=settings.QUALITY_JUDGE_TIMEOUT,
                    metadata={"purpose": "quality_judge"},
                )
            )
        except Exception as exc:
            logger.warning("[QualityJudge] local judge unavailable: %s", exc)
            return QualityJudgment(
                judged=False,
                rationale=f"Judge unavailable: {exc}",
                latency_ms=round((time.time() - started) * 1000, 2),
            )

        raw = (res.completion or "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return QualityJudgment(
                judged=False,
                rationale="Judge response was not parseable JSON.",
                latency_ms=round((time.time() - started) * 1000, 2),
            )

        try:
            parsed = json.loads(match.group(0))
        except (ValueError, TypeError):
            return QualityJudgment(
                judged=False,
                rationale="Judge response JSON failed to parse.",
                latency_ms=round((time.time() - started) * 1000, 2),
            )

        def _score(key: str) -> Optional[float]:
            try:
                val = float(parsed.get(key))
            except (TypeError, ValueError):
                return None
            return max(0.0, min(1.0, val))

        faithfulness = _score("faithfulness")
        relevance = _score("relevance")
        completeness = _score("completeness")

        if faithfulness is None and relevance is None and completeness is None:
            return QualityJudgment(
                judged=False,
                rationale="Judge returned no parseable scores.",
                latency_ms=round((time.time() - started) * 1000, 2),
            )

        return QualityJudgment(
            faithfulness=faithfulness,
            relevance=relevance,
            completeness=completeness,
            rationale=str(parsed.get("rationale", ""))[:300],
            judged=True,
            latency_ms=round((time.time() - started) * 1000, 2),
        )


quality_judge = QualityJudge()
