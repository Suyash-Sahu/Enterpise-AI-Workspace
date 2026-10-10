"""
Phase 30: Failure Attribution Module.

When a run produces a bad result, FailureAttributor identifies which agent
caused it and which failure category applies, replacing the blunt last-step
proxy used previously (supervisor.py:449 `plan.steps[-1]`).

Failure taxonomy (closed set):
    no_data               - source returned nothing
    wrong_data            - verifier caught a contradiction
    unsupported_claim     - claim not backed by retrieved evidence
    handoff_mismatch      - producer/consumer binding produced wrong type
    capability_misselected - routing chose the wrong handler for the task
    tool_error            - handler raised an internal exception
    timeout               - step hit the execution timeout
    injection_attempt_detected - prompt injection detected in content

Attribution algorithm (topological precedence):
    1. A step whose own per-step verification FAILED is the prime suspect.
    2. If several steps failed, the earliest in topological order wins --
       downstream failures are usually consequences of an upstream root cause.
    3. If no step failed but the final answer did, attribute to synthesis.
    4. If the final failure is 'unsupported_claims', attribute to the
       evidence-producing ancestor whose evidence was missing / contradictory.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from app.schemas.supervisor import PlanStep, SupervisorPlan

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Failure taxonomy
# ---------------------------------------------------------------------------

FAILURE_CATEGORIES: set[str] = {
    "no_data",
    "wrong_data",
    "unsupported_claim",
    "handoff_mismatch",
    "capability_misselected",
    "tool_error",
    "timeout",
    "injection_attempt_detected",
}


def _infer_category(step: PlanStep, verification_json: Optional[str]) -> str:
    """
    Infer the most specific failure category for a step.
    Reads from the persisted per-step verification report when available.
    """
    if step.status == "TIMEOUT":
        return "timeout"

    if verification_json:
        try:
            report = json.loads(verification_json)
            failures: list[str] = report.get("failures", [])
            text = " ".join(failures).lower()
            if "injection" in text or "prompt injection" in text:
                return "injection_attempt_detected"
            if "unsupported" in text or "unattributed" in text:
                return "unsupported_claim"
            if "contradict" in text or "conflict" in text:
                return "wrong_data"
            if "empty" in text or "no data" in text or "no result" in text:
                return "no_data"
            if "binding" in text or "handoff" in text or "mismatch" in text:
                return "handoff_mismatch"
            if "tool" in text or "exception" in text or "error" in text:
                return "tool_error"
            # Generic verification failure with no specific indicator
            return "wrong_data"
        except (ValueError, TypeError):
            pass

    # Fallback by step characteristics
    if step.capability in ("rag_search", "rag_answer", "database_query"):
        return "no_data"
    if step.capability in ("text_generation", "document_summary"):
        return "unsupported_claim"
    return "tool_error"


# ---------------------------------------------------------------------------
# Attribution result
# ---------------------------------------------------------------------------

@dataclass
class Attribution:
    """
    The result of running FailureAttributor.attribute().

    suspect_step_id  - the step_id of the step judged to be the root cause
    suspect_capability - the capability of the suspect step
    failure_category - one of FAILURE_CATEGORIES
    confidence       - 0.0-1.0: how certain the attribution is
    evidence         - list of human-readable justification strings
    """
    suspect_step_id: str
    suspect_capability: str
    failure_category: str
    confidence: float
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "suspect_step_id": self.suspect_step_id,
            "suspect_capability": self.suspect_capability,
            "failure_category": self.failure_category,
            "confidence": self.confidence,
            "evidence": self.evidence,
        }


# ---------------------------------------------------------------------------
# FailureAttributor
# ---------------------------------------------------------------------------

class FailureAttributor:
    """
    Implements the three-rule attribution algorithm (Phase 30).

    Usage:
        attributor = FailureAttributor()
        attribution = attributor.attribute(
            plan=plan,
            step_reports=step_reports,   # dict[step_id -> verification_json or None]
            final_report=final_report,   # dict from response_verifier.verify().to_dict()
        )
    """

    def attribute(
        self,
        plan: SupervisorPlan,
        step_reports: dict[str, Optional[str]],
        final_report: Optional[dict] = None,
    ) -> Attribution:
        """
        Attribute a run failure to a specific step + category.

        Parameters
        ----------
        plan         : SupervisorPlan, with steps whose .status is already set
        step_reports : mapping from step_id to verification_json (may be None)
        final_report : the dict produced by response_verifier.verify().to_dict()
                       -- only consulted if no step-level failure is found
        """
        steps = plan.steps

        # Build topological order: steps with no depends_on first, then by
        # their position in the plan list (which the scheduler guarantees is
        # consistent with the dependency order for a valid DAG).
        topo_order: dict[str, int] = {s.step_id: i for i, s in enumerate(steps)}

        # Rule 1 & 2: find the earliest-failing step in topological order
        failed_steps = [
            s for s in steps
            if s.status in ("FAILED", "TIMEOUT") and s.step_id != "step_synthesis"
        ]

        if failed_steps:
            # Sort by topological position (earliest = lowest index wins)
            failed_steps.sort(key=lambda s: topo_order.get(s.step_id, 9999))
            suspect = failed_steps[0]
            ver_json = step_reports.get(suspect.step_id)
            category = _infer_category(suspect, ver_json)
            evidence = [
                f"Step '{suspect.step_id}' ({suspect.capability}) "
                f"status={suspect.status} is the earliest failing node "
                f"in topological order (position {topo_order.get(suspect.step_id, '?')})."
            ]
            if len(failed_steps) > 1:
                evidence.append(
                    f"Additional failed steps (downstream, not blamed): "
                    f"{[s.step_id for s in failed_steps[1:]]}."
                )
            confidence = 0.85 if len(failed_steps) == 1 else 0.75
            logger.info(
                "[Attribution] Suspect: %s | Category: %s | Confidence: %.2f",
                suspect.step_id, category, confidence,
            )
            return Attribution(
                suspect_step_id=suspect.step_id,
                suspect_capability=suspect.capability,
                failure_category=category,
                confidence=confidence,
                evidence=evidence,
            )

        # Rule 3: no step failed; the final answer failed -> blame synthesis
        final_failures: list[str] = []
        if final_report:
            final_failures = final_report.get("failures", [])

        if final_failures:
            final_text = " ".join(final_failures).lower()
            if "unsupported" in final_text or "unattributed" in final_text:
                # Rule 4: trace unsupported claims to the evidence-producing ancestor
                # (the first rag/db step in topological order, as a proxy)
                evidence_steps = [
                    s for s in steps
                    if s.capability in (
                        "rag_search", "rag_answer", "database_query", "rag_answer"
                    )
                ]
                if evidence_steps:
                    evidence_steps.sort(key=lambda s: topo_order.get(s.step_id, 9999))
                    suspect = evidence_steps[0]
                    return Attribution(
                        suspect_step_id=suspect.step_id,
                        suspect_capability=suspect.capability,
                        failure_category="unsupported_claim",
                        confidence=0.65,
                        evidence=[
                            "Final answer had unsupported claims; attributed to earliest "
                            f"evidence-producing step '{suspect.step_id}' ({suspect.capability}).",
                            f"Final verification failures: {final_failures}",
                        ],
                    )

            # Generic final failure -> synthesis step
            return Attribution(
                suspect_step_id="step_synthesis",
                suspect_capability="text_generation",
                failure_category="wrong_data",
                confidence=0.55,
                evidence=[
                    "No individual step failed; final answer verification failed.",
                    f"Final verification failures: {final_failures}",
                ],
            )

        # Fallback: last step (matches the old proxy, keeps single-step behavior identical)
        if steps:
            last = steps[-1]
            ver_json = step_reports.get(last.step_id)
            category = _infer_category(last, ver_json)
            return Attribution(
                suspect_step_id=last.step_id,
                suspect_capability=last.capability,
                failure_category=category,
                confidence=0.4,
                evidence=["No verification failures found; falling back to last-step proxy (Phase 4 behavior)."],
            )

        # Empty plan edge case
        return Attribution(
            suspect_step_id="unknown",
            suspect_capability="unknown",
            failure_category="tool_error",
            confidence=0.0,
            evidence=["Plan has no steps; cannot attribute."],
        )


# ---------------------------------------------------------------------------
# Replay mode
# ---------------------------------------------------------------------------

def replay_attribution(
    plan_dict: dict,
    step_reports: dict[str, Optional[str]],
    final_report: Optional[dict] = None,
) -> Attribution:
    """
    Re-run attribution against a stored run dictionary without re-executing
    agents. Accepts the serialized form of a SupervisorPlan so attribution
    logic can be tuned against real recorded failures.
    """
    steps = [
        PlanStep(
            step_id=s["step_id"],
            capability=s["capability"],
            purpose=s.get("purpose", "capability"),
            depends_on=s.get("depends_on", []),
            input_template=s.get("input_template", {}),
            status=s.get("status", "FAILED"),
        )
        for s in plan_dict.get("steps", [])
    ]
    plan = SupervisorPlan(
        plan_id=plan_dict.get("plan_id", "replay"),
        request_id=plan_dict.get("request_id", "replay"),
        steps=steps,
        max_steps=plan_dict.get("max_steps", 5),
    )
    attributor = FailureAttributor()
    return attributor.attribute(plan=plan, step_reports=step_reports, final_report=final_report)


failure_attributor = FailureAttributor()
