"""
Privacy sensitivity classifier: a three-stage cascade with a fail-closed default.

Why a cascade rather than one trained model
-------------------------------------------
The error costs here are wildly asymmetric. A false negative sends confidential
content to a third-party API and is irreversible: you cannot un-send it, and in
a regulated setting it is a reportable incident. A false positive keeps a public
task local and costs a few cents and a few seconds. Any design that optimises
plain accuracy is therefore optimising the wrong objective.

That asymmetry drives three choices:

1. **Stage order is cheapest-and-surest first.** Regulated identifiers have
   checksums and fixed shapes, so a validated regex is both faster and more
   precise than any learned model. Stage 1 costs microseconds and settles the
   cases that matter most.

2. **Stages escalate, never average.** Each stage can only raise sensitivity,
   never lower what an earlier stage found. One private-key hit is not
   outvoted by three weak "looks public" signals.

3. **Abstention resolves to local.** If no stage is confident, the content is
   treated as CONFIDENTIAL. Uncertainty is not a reason to take a risk.

A fine-tuned transformer was rejected: the available labelled set is tiny, it
would need a GPU at request time, and it destroys the audit trail. A reviewer
can check "detector us_ssn fired at offset 214"; nobody can check a logit.
Stage 2 still gives the graded generalisation a learned model would, using the
embedding service that already exists, and the interface is narrow enough that
a trained model can replace stage 2 later without touching the router.

The LLM judge runs on the LOCAL model only, and calls the Ollama runtime
directly rather than going through runtime_service. Two reasons: sending
content to a cloud model to ask whether it is safe to send to a cloud model
defeats the entire mechanism, and routing through runtime_service would recurse
back into this classifier.
"""

from __future__ import annotations

import json
import logging
import math
import re
import time
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.privacy.contracts import (
    ClassificationResult,
    ClassifierStage,
    SensitivityLabel,
    Signal,
)
from app.privacy.patterns import scan

logger = logging.getLogger(__name__)

_LABEL_BY_VALUE = {lab.value: lab for lab in SensitivityLabel}


def _cosine(v1: list[float], v2: list[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = num1 = num2 = 0.0
    for a, b in zip(v1, v2):
        dot += a * b
        num1 += a * a
        num2 += b * b
    if num1 <= 0.0 or num2 <= 0.0:
        return 0.0
    return dot / ((num1 ** 0.5) * (num2 ** 0.5))


class PrivacyClassifier:
    """
    Stateless per call, except for a lazily built exemplar index used by stage 2.
    """

    def __init__(self) -> None:
        self._exemplar_vectors: list[tuple[list[float], SensitivityLabel]] = []
        self._exemplars_loaded = False

    # --- Stage 2 index ------------------------------------------------------

    def load_exemplars(self, exemplars: list[dict[str, Any]]) -> int:
        """
        Builds the nearest-neighbour index from labelled examples.

        Each exemplar is {"text": str, "label": "public"|"internal"|"confidential"}.
        Called at startup and from the evaluation harness. Embedding failures are
        tolerated per item: a partial index is still useful, and an empty index
        simply means stage 2 abstains and the cascade falls through to stage 3.
        """
        from app.rag.embeddings import embedding_service

        vectors: list[tuple[list[float], SensitivityLabel]] = []
        for item in exemplars:
            text = (item.get("text") or "").strip()
            raw_label = (item.get("label") or "").strip().lower()
            if not text or raw_label not in _LABEL_BY_VALUE:
                continue
            try:
                vec = embedding_service.generate_embedding(text)
            except Exception as exc:
                logger.warning("[PrivacyClassifier] exemplar embedding failed: %s", exc)
                continue
            if vec:
                vectors.append((vec, _LABEL_BY_VALUE[raw_label]))

        self._exemplar_vectors = vectors
        self._exemplars_loaded = True
        logger.info("[PrivacyClassifier] exemplar index built: %d vectors", len(vectors))
        return len(vectors)

    def _load_default_exemplars(self) -> None:
        """
        Loads the configured exemplar file on first use.

        Lazy rather than wired into application startup deliberately: the
        classifier is reached from the API, from pytest, from the evaluation
        harness and from one-off scripts, and a startup hook would only cover
        the first of those. An empty index caused by a missing file is not fatal
        — stage 2 abstains and the cascade falls through — but it *is* the
        difference between the cloud branch being reachable and not, so the
        outcome is logged either way.
        """
        self._exemplars_loaded = True  # set first: one attempt, not one per call

        path = Path(settings.PRIVACY_EXEMPLAR_PATH)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path

        if not path.exists():
            logger.warning(
                "[PrivacyClassifier] exemplar file %s not found. Stage 2 will "
                "abstain, so content without a rule hit fails closed to local.",
                path,
            )
            return

        try:
            with open(path, encoding="utf-8") as handle:
                exemplars = [json.loads(line) for line in handle if line.strip()]
        except (OSError, ValueError) as exc:
            logger.warning("[PrivacyClassifier] could not read %s: %s", path, exc)
            return

        self.load_exemplars(exemplars)

    @property
    def exemplar_count(self) -> int:
        return len(self._exemplar_vectors)

    # --- Stages -------------------------------------------------------------

    def _stage_rules(self, text: str) -> tuple[Optional[SensitivityLabel], list[Signal], float]:
        """
        Deterministic detectors. Returns the escalated label, the signals that
        fired, and a confidence derived from the strongest matching detector.
        """
        signals = scan(text)
        if not signals:
            return None, [], 0.0

        label = SensitivityLabel.escalate(*[s.label for s in signals])
        # Confidence comes from the strongest detector that agrees with the
        # escalated label, not from how many fired. Ten weak INTERNAL hits
        # should not look more certain than one validated card number.
        agreeing = [s.weight for s in signals if s.label == label]
        confidence = max(agreeing) if agreeing else 0.0
        return label, signals, confidence

    def _stage_embedding(self, text: str, k: int = 5) -> tuple[Optional[SensitivityLabel], float]:
        """
        Similarity-weighted k-NN over labelled exemplars.

        Confidence is the winning label's share of total similarity mass among
        the k neighbours, which behaves sensibly when neighbours disagree. If
        the nearest neighbour is not similar enough in absolute terms, the
        stage abstains rather than guessing from a distant match.
        """
        if not self._exemplars_loaded:
            self._load_default_exemplars()

        if not self._exemplar_vectors:
            return None, 0.0

        try:
            from app.rag.embeddings import embedding_service

            query_vec = embedding_service.generate_embedding(text)
        except Exception as exc:
            logger.warning("[PrivacyClassifier] query embedding failed: %s", exc)
            return None, 0.0

        if not query_vec:
            return None, 0.0

        scored = sorted(
            ((_cosine(query_vec, vec), lab) for vec, lab in self._exemplar_vectors),
            key=lambda pair: pair[0],
            reverse=True,
        )[:k]

        if not scored or scored[0][0] < settings.PRIVACY_KNN_MIN_SIMILARITY:
            return None, 0.0

        # Softmax over similarities rather than a linear sum, so confidence
        # tracks the *margin* between the nearest neighbour and the rest.
        #
        # Linear mass-share counts weak neighbours at close to their face value.
        # A query whose top match is 0.56 public and whose next four are ~0.20
        # internal is decisively public, but linear share reported only 0.59 and
        # the stage abstained. Exponential weighting with a small temperature
        # concentrates mass on genuinely near matches and reports ~0.89, while a
        # genuinely ambiguous neighbourhood (several matches at similar
        # distance) still comes out near chance and correctly abstains.
        #
        # PRIVACY_KNN_TEMPERATURE is a calibration knob: lower sharpens toward
        # nearest-neighbour-takes-all, higher approaches the linear behaviour.
        temperature = max(1e-6, settings.PRIVACY_KNN_TEMPERATURE)
        top_sim = scored[0][0]

        mass: dict[SensitivityLabel, float] = {}
        for sim, lab in scored:
            if sim <= 0.0:
                continue
            # Offset by the top similarity before exponentiating to keep the
            # values in a safe range; this cancels out in the normalisation.
            weight = math.exp((sim - top_sim) / temperature)
            mass[lab] = mass.get(lab, 0.0) + weight

        if not mass:
            return None, 0.0

        total = sum(mass.values())
        winner, winner_mass = max(mass.items(), key=lambda kv: kv[1])
        return winner, (winner_mass / total) if total > 0 else 0.0

    def _stage_llm_judge(self, text: str) -> tuple[Optional[SensitivityLabel], float]:
        """
        Local-model judge, used only when stages 1 and 2 both abstain.

        Calls ollama_runtime directly: routing this through runtime_service
        would re-enter the router and recurse, and a cloud judge would leak the
        very content it is being asked to protect.
        """
        if not settings.PRIVACY_LLM_JUDGE_ENABLED:
            return None, 0.0

        from app.runtime.local_runtime import ollama_runtime
        from app.schemas.runtime import RuntimeGenerateRequest, RuntimeMode

        prompt = (
            "You classify the sensitivity of enterprise content for data-residency "
            "routing. Answer with JSON only.\n\n"
            "Labels:\n"
            '- "public": safe to send to a third-party API. No personal data, no '
            "secrets, no internal-only business information.\n"
            '- "internal": company-private but not regulated. Internal processes, '
            "non-public projects, employee-directory-level detail.\n"
            '- "confidential": regulated or secret. Personal identifiers, health, '
            "financial or payroll data, credentials, legal-privileged material.\n\n"
            "If you are unsure between two labels, choose the more sensitive one.\n\n"
            'Respond exactly as: {"label": "<label>", "confidence": <0.0-1.0>}\n\n'
            f"Content:\n{text[: settings.PRIVACY_MAX_SCAN_CHARS]}"
        )

        try:
            res = ollama_runtime.generate(
                RuntimeGenerateRequest(
                    prompt=prompt,
                    execution_mode=RuntimeMode.LOCAL,
                    model=settings.PRIVACY_JUDGE_MODEL or None,
                    temperature=0.0,
                    max_tokens=64,
                    timeout=settings.PRIVACY_JUDGE_TIMEOUT,
                    metadata={"purpose": "privacy_classification"},
                )
            )
        except Exception as exc:
            logger.warning("[PrivacyClassifier] local judge unavailable: %s", exc)
            return None, 0.0

        raw = (res.completion or "").strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return None, 0.0
        try:
            parsed = json.loads(match.group(0))
        except (ValueError, TypeError):
            return None, 0.0

        label = _LABEL_BY_VALUE.get(str(parsed.get("label", "")).strip().lower())
        if label is None:
            return None, 0.0
        try:
            confidence = float(parsed.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        return label, max(0.0, min(1.0, confidence))

    # --- Entry point --------------------------------------------------------

    def classify(
        self,
        content: str,
        context: Optional[dict[str, Any]] = None,
    ) -> ClassificationResult:
        """
        Classifies `content`, returning a label with a confidence score.

        `context` may carry:
          - `declared_sensitivity`: a caller assertion (for example, the source
            connector already knows a document sits in an HR drive). Treated as
            a floor, never a ceiling: it can raise the label but never lower
            what the detectors found.
          - `privacy_bypass`: set by internal machinery (the judge itself,
            intent classification) to avoid recursion.
        """
        started = time.time()
        context = context or {}

        if context.get("privacy_bypass"):
            return ClassificationResult(
                label=SensitivityLabel.CONFIDENTIAL,
                confidence=1.0,
                stage=ClassifierStage.CALLER_ASSERTED,
                latency_ms=0.0,
                rationale="Internal call; pinned local without classification.",
            )

        text = (content or "")[: settings.PRIVACY_MAX_SCAN_CHARS]

        declared = _LABEL_BY_VALUE.get(
            str(context.get("declared_sensitivity", "")).strip().lower()
        )

        if not text.strip():
            # Nothing to inspect is not evidence of safety.
            floor = [declared] if declared else []
            return ClassificationResult(
                label=SensitivityLabel.escalate(*floor, SensitivityLabel.CONFIDENTIAL),
                confidence=1.0,
                stage=ClassifierStage.FAIL_CLOSED,
                abstained=True,
                latency_ms=round((time.time() - started) * 1000, 3),
                rationale="Empty content; fail-closed to local execution.",
            )

        # Stage 1 - deterministic detectors.
        rule_label, signals, rule_conf = self._stage_rules(text)
        if rule_label is not None and rule_conf >= settings.PRIVACY_RULE_CONFIDENCE:
            label = SensitivityLabel.escalate(
                *[lab for lab in (rule_label, declared) if lab is not None]
            )
            return ClassificationResult(
                label=label,
                confidence=rule_conf,
                stage=ClassifierStage.RULES,
                signals=signals,
                latency_ms=round((time.time() - started) * 1000, 3),
                rationale=(
                    "Matched deterministic detectors: "
                    + ", ".join(sorted({s.detector for s in signals}))
                ),
            )

        # Stage 2 - nearest-neighbour over labelled exemplars.
        knn_label, knn_conf = self._stage_embedding(text)
        if knn_label is not None and knn_conf >= settings.PRIVACY_KNN_CONFIDENCE:
            label = SensitivityLabel.escalate(
                *[lab for lab in (knn_label, rule_label, declared) if lab is not None]
            )
            return ClassificationResult(
                label=label,
                confidence=knn_conf,
                stage=ClassifierStage.EMBEDDING,
                signals=signals,
                latency_ms=round((time.time() - started) * 1000, 3),
                rationale=f"k-NN over {self.exemplar_count} exemplars.",
            )

        # Stage 3 - local LLM judge.
        judge_label, judge_conf = self._stage_llm_judge(text)
        if judge_label is not None and judge_conf >= settings.PRIVACY_JUDGE_CONFIDENCE:
            label = SensitivityLabel.escalate(
                *[
                    lab
                    for lab in (judge_label, knn_label, rule_label, declared)
                    if lab is not None
                ]
            )
            return ClassificationResult(
                label=label,
                confidence=judge_conf,
                stage=ClassifierStage.LLM_JUDGE,
                signals=signals,
                latency_ms=round((time.time() - started) * 1000, 3),
                rationale="Local LLM judge.",
            )

        # No stage cleared its threshold. Fail closed.
        observed = [
            lab
            for lab in (judge_label, knn_label, rule_label, declared)
            if lab is not None
        ]
        return ClassificationResult(
            label=SensitivityLabel.escalate(*observed, SensitivityLabel.CONFIDENTIAL),
            confidence=max(rule_conf, knn_conf, judge_conf),
            stage=ClassifierStage.FAIL_CLOSED,
            signals=signals,
            abstained=True,
            latency_ms=round((time.time() - started) * 1000, 3),
            rationale="No stage reached its confidence threshold; fail-closed to local.",
        )


privacy_classifier = PrivacyClassifier()
