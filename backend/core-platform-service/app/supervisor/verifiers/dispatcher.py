"""
Phase 29: verify_step dispatcher.

Routes a completed step's output to the correct type-specific verifier based
on its capability string. Unknown capabilities return UNVERIFIED (not FAILED)
so new capabilities don't silently break the pipeline until they get their
own verifier.

Respects VERIFICATION_MODE:
  - "off"         -> always return UNVERIFIED, write nothing.
  - "final_only"  -> always return UNVERIFIED from this dispatcher
                     (the whole-answer ResponseVerifier still runs as before).
  - "per_step"    -> dispatch to the correct type checker.

SupervisorIntegrationNote: every ExecutionHandler wraps its agent output
under a "result" key (app/execution/contracts.py -- e.g. DatabaseQueryHandler
returns {"result": DatabaseResult.dump(), "provider", "model", ...}). The
verifiers check the *agent output shape*, so the dispatcher unwraps one
"result" envelope level before dispatching, and passes the run's owner_id
through for the owner-scope checks (opaque tenant string, same one the
execution layer uses throughout -- resolve_user_id()'s int is NOT required
here; verification must never crash a run that never touches an approval).
"""
from __future__ import annotations

from typing import Any, Optional

from app.core.config import settings
from app.supervisor.verifier import VerificationReport
from app.supervisor.verifiers.checkers import (
    draft_verifier,
    evidence_verifier,
    inbox_verifier,
    reconciliation_verifier,
    rowset_verifier,
    schedule_verifier,
)

# Map capability -> verifier instance. Keys are the real TaskRegistry
# capability names (app/execution/registry.py), not aspirational ones.
#
# Deliberately absent: gmail.send (its handler output legitimately records
# sent=True -- it IS the send, post-approval -- and a DraftVerifier "a draft
# must not claim it was sent" check would false-fail every real send; it is
# protected by the approval gate, not by output verification),
# workgraph.create_task / meeting.extract / digest.daily / text_generation
# (no declared agent output shape to verify mechanically yet -> UNVERIFIED).
_VERIFIER_MAP = {
    "database_query": rowset_verifier,
    "database_report": rowset_verifier,
    "rag_search": evidence_verifier,
    "rag_answer": evidence_verifier,
    "document_summary": evidence_verifier,
    "inbox.classify": inbox_verifier,
    "inbox.draft_reply": draft_verifier,
    # ScheduleView / Reconciliation outputs reach the supervisor through
    # decomposed multi-step plans; map both the agent-role names and the
    # capability spellings those plans use.
    "calendar_view": schedule_verifier,
    "schedule_view": schedule_verifier,
    "research_reconciliation": reconciliation_verifier,
    "reconciliation": reconciliation_verifier,
}


def _unwrap_result_envelope(output: Any) -> Any:
    """Peel one ExecutionHandler "result" envelope level when present."""
    if isinstance(output, dict) and "result" in output and isinstance(output["result"], (dict, list)):
        return output["result"]
    return output


def verify_step(
    capability: str,
    inputs: dict[str, Any],
    output: Any,
    evidence: list[str] | None = None,
    owner_id: Optional[str] = None,
) -> VerificationReport:
    """
    Dispatch a completed step's output to the right type-specific verifier.

    Returns a `VerificationReport` in all cases -- callers do not need to
    handle None.
    """
    mode = settings.VERIFICATION_MODE.lower()

    if mode in ("off", "final_only"):
        return VerificationReport(
            status="UNVERIFIED",
            confidence=0.5,
            checks={"mode": mode},
            failures=[],
        )

    verifier = _VERIFIER_MAP.get(capability)
    if verifier is None:
        return VerificationReport(
            status="UNVERIFIED",
            confidence=0.5,
            checks={"reason": f"no verifier registered for capability '{capability}'"},
            failures=[],
        )

    output = _unwrap_result_envelope(output)
    if not isinstance(output, dict):
        return VerificationReport(
            status="UNVERIFIED",
            confidence=0.5,
            checks={"reason": f"step output for '{capability}' is not a dict"},
            failures=[],
        )

    return verifier.verify(
        inputs=inputs or {},
        output=output,
        evidence=evidence or [],
        owner_id=owner_id,
    )


def verification_mode_for_run(context: Any) -> str:
    """
    Effective verification mode for one run.

    `context.verification_enabled=False` (the existing per-run ablation
    toggle, used by every evaluation harness) forces "off": a run that
    opted out of verification must not silently gain a per-step verifier
    just because the deployment default changed. Otherwise the configured
    mode applies.
    """
    if not getattr(context, "verification_enabled", True):
        return "off"
    return settings.VERIFICATION_MODE.lower()


__all__ = ["verify_step", "verification_mode_for_run"]
