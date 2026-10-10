"""
Response verification.

Replaces the previous arrangement, where `verification_enabled` was written
into the evaluation config and never read, and `verification_status` was set to
"PASSED" whenever the run had not crashed. That made the verification ablation
arm identical to the arm without it, and made the reported quality score a
constant rather than a measurement.

The checks here are deliberately modest and mechanical. They do not attempt to
judge whether an answer is *correct* — nothing available at this layer can
establish that. They establish whether the answer is *supported*: that it is
non-degenerate, that claims which should be grounded in retrieved passages
share vocabulary with those passages, and that a stated count does not
contradict the rows actually returned. Those are checkable, cheap and honest,
and each one fails in a way that can be pointed at.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Answers that are technically non-empty but carry no information. A generation
# that degenerates to one of these should not count as a success.
_DEGENERATE_PATTERNS = (
    re.compile(r"(?i)^\s*(?:n/?a|none|unknown|no answer|i (?:don'?t|do not) know)\s*[.!]?\s*$"),
    re.compile(r"(?i)^\s*(?:sorry|unfortunately)[^.]*(?:cannot|can't|unable)[^.]*\.?\s*$"),
    re.compile(r"(?i)^\s*(?:error|failed|exception)\b"),
)

_STOPWORDS = frozenset(
    """a an and are as at be by for from has have in is it its of on or that the
    to was were will with this these those there their them they what which who
    how when where why can could should would may might do does did not no yes
    you your we our us i me my if then than so such about into over under""".split()
)


def _tokens(text: str) -> set[str]:
    return {
        tok
        for tok in re.findall(r"[a-z0-9][a-z0-9\-_]{2,}", (text or "").lower())
        if tok not in _STOPWORDS
    }


@dataclass
class VerificationReport:
    status: str  # PASSED | FAILED | UNVERIFIED
    confidence: float
    checks: dict[str, Any] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "PASSED"

    @property
    def confidence_band(self) -> str:
        """
        CDRP confidence bands:
        - "critical": degenerate output (empty/refusal/error).
        - "low": status == "FAILED" (and not critical).
        - "high": status == "PASSED" and confidence >= 0.85.
        - "medium": passed, but under confidence threshold (0.85).
        """
        if not self.checks.get("non_degenerate", True):
            return "critical"
        if self.status == "FAILED":
            return "low"
        if self.status == "PASSED" and self.confidence >= 0.85:
            return "high"
        return "medium"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "confidence": round(self.confidence, 4),
            "confidence_band": self.confidence_band,
            "checks": self.checks,
            "failures": self.failures,
        }


class ResponseVerifier:

    # Fraction of the answer's content words that must also appear in the
    # retrieved passages before a grounded answer is considered supported.
    # A calibration knob: raise it to make verification stricter, and report
    # the value used alongside any verification numbers.
    GROUNDING_THRESHOLD = 0.25

    # Capabilities whose answers are supposed to be grounded in retrieved text.
    # Free generation is not, so grounding is not checked for it.
    GROUNDED_CAPABILITIES = frozenset({"rag_answer", "rag_search", "document_summary"})

    def verify(
        self,
        answer: str,
        aggregated_data: dict[str, Any],
        sources: list[dict[str, Any]],
    ) -> VerificationReport:
        checks: dict[str, Any] = {}
        failures: list[str] = []

        # 1. Non-degenerate output.
        text = (answer or "").strip()
        non_empty = bool(text) and not any(p.match(text) for p in _DEGENERATE_PATTERNS)
        checks["non_degenerate"] = non_empty
        if not non_empty:
            failures.append("Answer is empty or carries no information.")

        capabilities = {
            step.get("capability")
            for step in aggregated_data.values()
            if isinstance(step, dict)
        }
        needs_grounding = bool(capabilities & self.GROUNDED_CAPABILITIES)
        checks["grounding_applicable"] = needs_grounding

        # 2. Grounding: does the answer share vocabulary with what was retrieved?
        grounding_ratio: Optional[float] = None
        if needs_grounding:
            if not sources:
                failures.append("Grounded capability produced no sources to support the answer.")
                checks["has_sources"] = False
            else:
                checks["has_sources"] = True
                source_tokens: set[str] = set()
                for src in sources:
                    for key in ("content", "text", "snippet", "source"):
                        val = src.get(key)
                        if isinstance(val, str):
                            source_tokens |= _tokens(val)

                answer_tokens = _tokens(text)
                if answer_tokens and source_tokens:
                    overlap = answer_tokens & source_tokens
                    grounding_ratio = len(overlap) / len(answer_tokens)
                    if grounding_ratio < self.GROUNDING_THRESHOLD:
                        failures.append(
                            f"Only {grounding_ratio:.0%} of answer terms appear in the "
                            f"retrieved passages (threshold {self.GROUNDING_THRESHOLD:.0%})."
                        )
                elif not source_tokens:
                    # Sources exist but carry no readable text, so grounding
                    # cannot be assessed either way.
                    grounding_ratio = None
        checks["grounding_ratio"] = (
            round(grounding_ratio, 4) if grounding_ratio is not None else None
        )

        # 3. Numeric consistency against database results.
        consistency_ok = self._check_row_counts(text, aggregated_data)
        checks["row_count_consistent"] = consistency_ok
        if consistency_ok is False:
            failures.append("Answer states a count that disagrees with the rows returned.")

        # Confidence is the mean of the checks that were actually applicable,
        # so a task with nothing to ground against is not penalised for it.
        components: list[float] = [1.0 if non_empty else 0.0]
        if needs_grounding:
            if grounding_ratio is not None:
                components.append(min(1.0, grounding_ratio / self.GROUNDING_THRESHOLD))
            else:
                components.append(1.0 if checks.get("has_sources") else 0.0)
        if consistency_ok is not None:
            components.append(1.0 if consistency_ok else 0.0)

        confidence = sum(components) / len(components) if components else 0.0
        status = "FAILED" if (not non_empty or failures) else "PASSED"

        return VerificationReport(
            status=status,
            confidence=confidence,
            checks=checks,
            failures=failures,
        )

    @staticmethod
    def _check_row_counts(
        answer: str, aggregated_data: dict[str, Any]
    ) -> Optional[bool]:
        """
        Returns True/False when a database step reported a row count and the
        answer makes a claim about it, None when the check does not apply.

        Only the specific contradiction of claiming rows were found when none
        were, and vice versa, is flagged. Comparing arbitrary numbers in prose
        against a row count produces false positives, so it is not attempted.
        """
        row_counts = [
            step["output"].get("row_count", len(step["output"].get("rows", [])))
            for step in aggregated_data.values()
            if isinstance(step, dict)
            and step.get("capability") == "database_query"
            and isinstance(step.get("output"), dict)
        ]
        if not row_counts:
            return None

        total_rows = sum(row_counts)
        claims_none = re.search(
            r"(?i)\b(?:no|zero|none|not any)\s+(?:rows?|records?|results?|entries|matches)\b",
            answer,
        )

        if total_rows == 0:
            # Saying nothing was found is correct here; claiming a positive
            # count is not.
            positive_claim = re.search(
                r"\b([1-9]\d*)\s+(?:rows?|records?|results?)\b", answer
            )
            return not positive_claim
        return not bool(claims_none)


response_verifier = ResponseVerifier()
