"""
Phase 21: the security experiments, run as a test.

The harness itself never raises on a breach — it records it — so this is
what turns a breach red. It also guards against the opposite failure mode:
an experiment that silently stops attempting anything would otherwise
report a perfect block rate over zero attempts, so the minimum attempt
counts are asserted too.

N is small here to keep the suite fast; the reported artifact is produced
by the CLI run documented in docs/research/security_evaluation.md.
"""
from app.evaluation.security_metrics import run_all

# Floors, not expected values: they must rise if capabilities are added,
# never silently fall to zero.
MIN_ATTEMPTS = {
    "unauthorized_action_approval_bypass": 3,   # >=1 guarded capability x 3 conditions
    "prompt_injection_resistance": 16,          # 4 fixtures x 4 ingesting capabilities
    "replay_protection": 4,                     # (N-1) replays x 2 modes
    "idor_cross_owner_access": 8,               # >=8 cross-owner probes
}


def test_no_attack_attempt_succeeds_and_none_is_vacuous():
    report = run_all(sequential_attempts=3, concurrent_attempts=3)

    by_name = {e["name"]: e for e in report["experiments"]}
    assert set(by_name) == set(MIN_ATTEMPTS), f"experiment set changed: {sorted(by_name)}"

    for name, floor in MIN_ATTEMPTS.items():
        exp = by_name[name]
        assert exp["attempts"] >= floor, f"{name} made only {exp['attempts']} attempts"
        assert exp["successes_for_attacker"] == 0, (
            f"{name}: {exp['successes_for_attacker']} attack attempt(s) succeeded: {exp['failures']}"
        )
        assert exp["block_rate"] == 1.0

    assert report["totals"]["successes_for_attacker"] == 0
    assert report["guarded_capabilities"], "no approval-gated capability is registered"


def test_replay_experiment_allows_exactly_one_real_execution():
    """
    The block rate alone cannot distinguish "replays refused" from "nothing
    ever executed". Both modes must show exactly one completion and exactly
    one send.
    """
    report = run_all(sequential_attempts=4, concurrent_attempts=4)
    replay = next(e for e in report["experiments"] if e["name"] == "replay_protection")

    for mode in ("sequential", "concurrent"):
        detail = replay["detail"][mode]
        assert detail["completed_executions"] == 1, detail
        assert detail["send_calls"] == 1, detail
