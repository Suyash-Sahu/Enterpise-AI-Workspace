"""
Privacy-constrained router.

The routing problem is stated as constrained minimisation, not as scoring:

    minimise   estimated_cost(m)
    subject to placement(m) in allowed(classification)      <- hard
               est_latency(m) <= latency_budget             <- soft, relaxable
               quality(m)     >= quality_floor              <- soft, relaxable

The privacy constraint is the only hard one. It is applied by *removing*
candidates from the feasible set before any scoring happens, so no cost or
latency advantage can ever outweigh it. This is the structural difference from
a weighted-score router, where a large enough cost saving can always overwhelm
a privacy penalty term. Here there is no exchange rate between dollars and
disclosure.

The soft constraints relax in a fixed order when they would empty the feasible
set: latency budget first, then quality floor. The privacy constraint never
relaxes. If it empties the set, that is an error, not a reason to widen.

This module deliberately never inspects content. It receives a
ClassificationResult and works only from the label and confidence, which keeps
the classifier independently evaluable (precision/recall against labels) and
the router independently evaluable (placement against an oracle).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import settings
from app.privacy.classifier import privacy_classifier
from app.privacy.contracts import (
    ClassificationResult,
    ModelCandidate,
    Placement,
    RoutingDecision,
    SensitivityLabel,
)

logger = logging.getLogger(__name__)

_LABEL_BY_VALUE = {lab.value: lab for lab in SensitivityLabel}


class PrivacyConstrainedRouter:

    # --- Feasible set -------------------------------------------------------

    @staticmethod
    def allowed_placements(
        classification: ClassificationResult,
        max_cloud_label: Optional[str] = None,
    ) -> list[Placement]:
        """
        The hard constraint. Cloud is permitted only when the classified label
        is at or below the configured maximum cloud tier AND the classifier was
        confident enough to say so.

        Both conditions matter. Without the confidence test, a low-confidence
        PUBLIC guess would be enough to export data; a guess is not a basis for
        disclosure. Local is always feasible, which is what guarantees the
        feasible set is never empty.

        `max_cloud_label` overrides the configured tier. Its only legitimate use
        is the evaluation harness building the unconstrained ALWAYS_CLOUD
        baseline; production callers leave it None.
        """
        # RESTRICTED is an absolute floor: not even the evaluation harness's
        # unconstrained-baseline override can move it to cloud. Every other
        # tier passes through the override below; carving this one out first
        # is what makes "RESTRICTED never routes cloud" true under any
        # scoring weights, not just under the default production config.
        if classification.label is SensitivityLabel.RESTRICTED:
            return [Placement.LOCAL]

        max_cloud = _LABEL_BY_VALUE.get(
            str(max_cloud_label or settings.PRIVACY_MAX_CLOUD_LABEL).strip().lower(),
            SensitivityLabel.PUBLIC,
        )
        # An override that disables the constraint also disables the confidence
        # gate; otherwise the baseline would still be partly constrained and
        # would not be a clean comparison point.
        if max_cloud is SensitivityLabel.CONFIDENTIAL:
            return [Placement.LOCAL, Placement.CLOUD]

        cloud_ok = (
            classification.label.rank <= max_cloud.rank
            and classification.confidence >= settings.PRIVACY_CLOUD_CONFIDENCE
            and not classification.abstained
        )
        return [Placement.LOCAL, Placement.CLOUD] if cloud_ok else [Placement.LOCAL]

    @staticmethod
    def candidates() -> list[ModelCandidate]:
        """
        Builds the candidate set from the configured model profiles.

        Local cost is not zero. Amortised hardware and energy are folded into
        the local per-1k figures, because a router that prices local execution
        at zero will always choose local and any 'cost saving' it reports is a
        tautology rather than a finding.
        """
        out: list[ModelCandidate] = []
        # Development switch (settings.RUNTIME_CLOUD_ENABLED, Stage D). Disabling
        # cloud is expressed as "there are no cloud models to choose from", not
        # as a change to the privacy constraint: allowed_placements() still
        # returns exactly what it returned before, and every rejection reason it
        # records is still the real one. The feasible set simply has no cloud
        # member to score, so route() selects local by ordinary cost
        # minimisation rather than by a special case. Nothing about the hard
        # constraint, the confidence gate or the relaxation order is touched.
        placements = [(Placement.LOCAL, settings.RUNTIME_MODEL_PROFILES_LOCAL)]
        if settings.RUNTIME_CLOUD_ENABLED:
            placements.append((Placement.CLOUD, settings.RUNTIME_MODEL_PROFILES_CLOUD))
        for placement, profiles in placements:
            for model, prof in profiles.items():
                out.append(
                    ModelCandidate(
                        model=model,
                        placement=placement,
                        cost_per_1k_input=float(prof["cost_per_1k_input"]),
                        cost_per_1k_output=float(prof["cost_per_1k_output"]),
                        est_latency_ms=float(prof["est_latency_ms"]),
                        quality=float(prof["quality"]),
                    )
                )
        return out

    # --- Decision -----------------------------------------------------------

    def route(
        self,
        content: str,
        context: Optional[dict[str, Any]] = None,
        *,
        classification: Optional[ClassificationResult] = None,
        est_input_tokens: int = 0,
        est_output_tokens: int = 0,
        latency_budget_ms: Optional[float] = None,
        quality_floor: Optional[float] = None,
        requested_model: Optional[str] = None,
        max_cloud_label: Optional[str] = None,
    ) -> RoutingDecision:
        """
        Resolves content to a concrete (placement, model) pair.

        Pass `classification` to reuse an existing verdict rather than
        reclassifying, which the evaluation harness does when sweeping router
        thresholds against a fixed classifier output.
        """
        context = context or {}
        if classification is None:
            classification = privacy_classifier.classify(content, context)

        allowed = self.allowed_placements(classification, max_cloud_label)
        budget = (
            latency_budget_ms
            if latency_budget_ms is not None
            else settings.ROUTER_LATENCY_BUDGET_MS
        )
        floor = quality_floor if quality_floor is not None else settings.ROUTER_QUALITY_FLOOR

        in_tokens = est_input_tokens or self._estimate_tokens(content)
        out_tokens = est_output_tokens or settings.ROUTER_DEFAULT_OUTPUT_TOKENS

        rejected: list[dict[str, Any]] = []
        feasible: list[ModelCandidate] = []

        for cand in self.candidates():
            if requested_model and cand.model != requested_model:
                continue
            if cand.placement not in allowed:
                rejected.append(
                    {
                        "model": cand.model,
                        "placement": cand.placement.value,
                        "reason": "privacy_constraint",
                        "detail": (
                            f"content classified {classification.label.value} "
                            f"(confidence {classification.confidence:.2f}); "
                            "cloud placement not permitted"
                        ),
                    }
                )
                continue
            feasible.append(cand)

        if not feasible:
            # Only reachable if the allowlist and the profile table disagree,
            # or a requested_model was filtered out. Fall back to the default
            # local model rather than widening the privacy constraint.
            logger.warning(
                "[Router] no feasible candidate for label=%s; defaulting to local.",
                classification.label.value,
            )
            return RoutingDecision(
                placement=Placement.LOCAL,
                model=settings.OLLAMA_DEFAULT_MODEL,
                classification=classification,
                allowed_placements=allowed,
                rejected=rejected,
                # No candidate was actually scored, so there is no placement
                # confidence to report -- this is a fallback, not a choice.
                routing_confidence=0.0,
                constraint_binding=Placement.CLOUD not in allowed,
                reason="No candidate satisfied the constraints; defaulted to local.",
            )

        # Soft constraints, relaxed in order if they would empty the set.
        pool, relaxations = self._apply_soft_constraints(
            feasible, budget, floor, rejected
        )

        # Objective: cheapest first, then fastest as tie-break.
        winner = min(
            pool,
            key=lambda c: (
                round(c.estimated_cost(in_tokens, out_tokens), 8),
                c.est_latency_ms,
            ),
        )

        for cand in pool:
            if cand is winner:
                continue
            rejected.append(
                {
                    "model": cand.model,
                    "placement": cand.placement.value,
                    "reason": "higher_cost",
                    "detail": (
                        f"est ${cand.estimated_cost(in_tokens, out_tokens):.6f} "
                        f"vs winner ${winner.estimated_cost(in_tokens, out_tokens):.6f}"
                    ),
                }
            )

        reason = (
            f"{classification.label.value} content "
            f"(stage={classification.stage.value}, conf={classification.confidence:.2f}); "
            f"allowed={[p.value for p in allowed]}; cheapest feasible candidate"
        )
        if relaxations:
            reason += f"; relaxed={','.join(relaxations)}"

        return RoutingDecision(
            placement=winner.placement,
            model=winner.model,
            classification=classification,
            allowed_placements=allowed,
            rejected=rejected,
            estimated_cost_usd=winner.estimated_cost(in_tokens, out_tokens),
            estimated_latency_ms=winner.est_latency_ms,
            predicted_quality=winner.quality,
            # Zero disclosure risk whenever nothing leaves the machine; for a
            # cloud placement, risk is exactly the classifier's own
            # uncertainty, since a wrong PUBLIC call is the only way a cloud
            # placement becomes a disclosure.
            risk=0.0 if winner.placement is Placement.LOCAL else round(1.0 - classification.confidence, 4),
            # 1.0 minus a penalty per soft constraint that had to relax --
            # each relaxation means the router compromised rather than found
            # a candidate that cleanly satisfied what was asked.
            routing_confidence=max(0.0, 1.0 - 0.25 * len(relaxations)),
            constraint_binding=Placement.CLOUD not in allowed,
            reason=reason,
        )

    # --- Helpers ------------------------------------------------------------

    @staticmethod
    def _apply_soft_constraints(
        feasible: list[ModelCandidate],
        budget: float,
        floor: float,
        rejected: list[dict[str, Any]],
    ) -> tuple[list[ModelCandidate], list[str]]:
        """
        Filters by latency budget then quality floor, skipping either filter if
        applying it would leave nothing. Records which filters were relaxed so
        the decision stays explainable.
        """
        relaxations: list[str] = []

        within_budget = [c for c in feasible if c.est_latency_ms <= budget]
        if within_budget:
            for c in feasible:
                if c not in within_budget:
                    rejected.append(
                        {
                            "model": c.model,
                            "placement": c.placement.value,
                            "reason": "latency_budget",
                            "detail": f"{c.est_latency_ms:.0f}ms > {budget:.0f}ms budget",
                        }
                    )
            pool = within_budget
        else:
            relaxations.append("latency_budget")
            pool = feasible

        above_floor = [c for c in pool if c.quality >= floor]
        if above_floor:
            for c in pool:
                if c not in above_floor:
                    rejected.append(
                        {
                            "model": c.model,
                            "placement": c.placement.value,
                            "reason": "quality_floor",
                            "detail": f"quality {c.quality:.2f} < floor {floor:.2f}",
                        }
                    )
            pool = above_floor
        else:
            relaxations.append("quality_floor")

        return pool, relaxations

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """
        ~4 characters per token. Deliberately crude: it only needs to rank
        candidates consistently, and every candidate is scored on the same
        estimate, so the comparison is unaffected by the constant.
        """
        return max(1, len(text or "") // 4)


privacy_router = PrivacyConstrainedRouter()
