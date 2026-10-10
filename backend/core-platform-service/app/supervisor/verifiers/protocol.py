"""
Phase 29: StepVerifier protocol and VerificationReport.

Re-exports VerificationReport from the parent verifier module so callers
always see the same class regardless of which module they import from.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# Re-use the existing VerificationReport from the parent module.
from app.supervisor.verifier import VerificationReport


@runtime_checkable
class StepVerifier(Protocol):
    """
    Structural protocol every per-type verifier must satisfy.

    `inputs`  — the resolved_input dict used to call the agent.
    `output`  — the step result dict (PlanStep.result, usually exec_res.result).
    `evidence`— list of evidence strings (chunk ids, message ids, …) produced
                by the agent, when available.

    Returns a `VerificationReport` — the same shape as the whole-answer
    verifier, so nothing downstream needs a new vocabulary.
    """

    def verify(
        self,
        inputs: dict[str, Any],
        output: dict[str, Any],
        evidence: list[str],
    ) -> VerificationReport:
        ...


__all__ = ["StepVerifier", "VerificationReport"]
