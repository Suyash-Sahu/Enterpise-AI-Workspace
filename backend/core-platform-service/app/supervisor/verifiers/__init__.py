"""
Phase 29: Per-step verification package.

`StepVerifier` is a structural protocol -- any object with a `verify` method
matching the signature works, no ABC inheritance required.

`verify_step` is the single public entry point: given a capability name and
step output dict, it dispatches to the right type-specific verifier and
returns a `VerificationReport`.

`verification_mode_for_run(context)` resolves the effective VERIFICATION_MODE
for one run ("off" | "final_only" | "per_step"), honoring the run's
verification_enabled toggle.
"""
from app.supervisor.verifiers.protocol import StepVerifier, VerificationReport
from app.supervisor.verifiers.dispatcher import verify_step, verification_mode_for_run

__all__ = ["StepVerifier", "VerificationReport", "verify_step", "verification_mode_for_run"]
