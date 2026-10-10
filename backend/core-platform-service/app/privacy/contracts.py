"""
Privacy-constrained routing — core types.

The split enforced here is the whole point of the design: the *classifier*
decides how sensitive content is, and the *router* decides where it may run.
The router never inspects content. That means the two can be evaluated
independently — the classifier against labelled data (precision/recall), the
router against a placement oracle — and a routing bug can never be mistaken
for a classification bug.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SensitivityLabel(str, Enum):
    """
    Ordered sensitivity tiers. Order matters: `escalate()` and the fail-closed
    default both rely on CONFIDENTIAL being the second-highest, RESTRICTED the
    maximum.
    """

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    # AMOF-X Phase 3: live credential material (a private key, an active API
    # key, a DB connection string with embedded credentials). Distinct from
    # CONFIDENTIAL because the failure mode is categorically worse: leaking a
    # regulated identifier (an SSN, a card number) is a privacy violation;
    # leaking a credential is an ongoing compromise -- an attacker can act as
    # the victim, not just learn about them. See app/privacy/patterns.py for
    # exactly which detectors carry this label. RESTRICTED is the one tier the
    # evaluation harness's unconstrained-baseline override cannot reach past
    # (app/privacy/router.py::allowed_placements) -- every other tier can be
    # deliberately unclamped for the ALWAYS_CLOUD baseline; this one can't.
    RESTRICTED = "restricted"

    @property
    def rank(self) -> int:
        return _LABEL_RANK[self]

    @classmethod
    def escalate(cls, *labels: "SensitivityLabel") -> "SensitivityLabel":
        """
        Returns the most sensitive of the given labels.

        Every stage of the classifier combines its findings this way rather than
        averaging or voting. One high-precision detector firing on a private key
        must not be diluted by three weak signals saying "looks public".
        """
        if not labels:
            return cls.CONFIDENTIAL
        return max(labels, key=lambda lab: lab.rank)


_LABEL_RANK: dict[SensitivityLabel, int] = {
    SensitivityLabel.PUBLIC: 0,
    SensitivityLabel.INTERNAL: 1,
    SensitivityLabel.CONFIDENTIAL: 2,
    SensitivityLabel.RESTRICTED: 3,
}


class Placement(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"


class ClassifierStage(str, Enum):
    """Which stage of the cascade produced the decision. Recorded for analysis."""

    RULES = "rules"
    EMBEDDING = "embedding"
    LLM_JUDGE = "llm_judge"
    FAIL_CLOSED = "fail_closed"
    CALLER_ASSERTED = "caller_asserted"


@dataclass(frozen=True)
class Signal:
    """One detector firing. Kept for audit trails and error analysis."""

    detector: str
    label: SensitivityLabel
    # Where in the text it matched. The matched text itself is deliberately NOT
    # stored: these records get logged, and logging the credit card number you
    # just detected would be its own breach.
    span: tuple[int, int]
    weight: float = 1.0


@dataclass
class ClassificationResult:
    label: SensitivityLabel
    confidence: float
    stage: ClassifierStage
    signals: list[Signal] = field(default_factory=list)
    latency_ms: float = 0.0
    # True when no stage reached its confidence threshold and the fail-closed
    # default was applied. Tracked separately from confidence because an
    # abstention is a different failure mode than a low-confidence guess.
    abstained: bool = False
    rationale: str = ""

    @property
    def detector_names(self) -> list[str]:
        return sorted({s.detector for s in self.signals})

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "label": self.label.value,
            "confidence": round(self.confidence, 4),
            "stage": self.stage.value,
            "detectors": self.detector_names,
            "abstained": self.abstained,
            "latency_ms": round(self.latency_ms, 2),
            "rationale": self.rationale,
        }


@dataclass
class ModelCandidate:
    """A model the router may choose, with the numbers it is scored on."""

    model: str
    placement: Placement
    # USD per 1k tokens. Local models are NOT free: the figure amortises
    # hardware and energy, because a router that treats local as zero-cost will
    # always pick local and the cost comparison becomes a tautology.
    cost_per_1k_input: float
    cost_per_1k_output: float
    est_latency_ms: float
    # Rough capability score in [0,1], used only as a floor check. This is a
    # calibration knob, not a measurement — retune it per deployment.
    quality: float

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            (input_tokens / 1000.0) * self.cost_per_1k_input
            + (output_tokens / 1000.0) * self.cost_per_1k_output
        )


@dataclass
class RoutingDecision:
    """
    The complete record of one routing decision, including the options that were
    rejected and why. This is what makes the non-leakage claim checkable after
    the fact rather than merely asserted.
    """

    placement: Placement
    model: str
    classification: ClassificationResult
    allowed_placements: list[Placement]
    rejected: list[dict[str, Any]] = field(default_factory=list)
    estimated_cost_usd: float = 0.0
    estimated_latency_ms: float = 0.0
    # The winning candidate's quality score ([0,1], see ModelCandidate.quality).
    # AMOF-X Phase 3: separated out from the winner so the structured decision
    # object carries predicted_quality directly rather than requiring a caller
    # to re-look-up the candidate by model name.
    predicted_quality: float = 0.0
    # Residual disclosure risk of *this placement choice*, in [0,1]. Zero
    # whenever placement is LOCAL: nothing left the machine, so there is no
    # disclosure risk regardless of how confident the classification was.
    # For CLOUD, risk is the classifier's own uncertainty (1 - confidence) --
    # the chance the classification was wrong is exactly the chance this
    # placement was a mistake, since a wrong PUBLIC call is the only way a
    # cloud placement becomes a disclosure.
    risk: float = 0.0
    # Confidence in the *placement/model* choice itself, distinct from
    # classification.confidence (which is confidence in the *content label*).
    # 1.0 when every soft constraint (latency budget, quality floor) was
    # satisfied without relaxing; each relaxation lowers it, because the
    # router had to compromise between what was asked for and what was
    # feasible. See app/privacy/router.py::route for where this is computed.
    routing_confidence: float = 0.0
    # True when the privacy constraint — not cost or latency — determined the
    # outcome. The fraction of decisions where this is True is the headline
    # number for how much the constraint actually binds on a given workload.
    constraint_binding: bool = False
    reason: str = ""

    def to_audit_dict(self) -> dict[str, Any]:
        return {
            "placement": self.placement.value,
            "model": self.model,
            "allowed_placements": [p.value for p in self.allowed_placements],
            "constraint_binding": self.constraint_binding,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "estimated_latency_ms": round(self.estimated_latency_ms, 1),
            "predicted_quality": round(self.predicted_quality, 4),
            "risk": round(self.risk, 4),
            "routing_confidence": round(self.routing_confidence, 4),
            "reason": self.reason,
            "rejected": self.rejected,
            "classification": self.classification.to_audit_dict(),
        }
