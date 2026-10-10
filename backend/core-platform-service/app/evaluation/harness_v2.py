"""
End-to-end harness: classifier + router + baselines on the v2 privacy corpus,
across independent stratified seeds, with a pre-flight check that refuses to
grind through hundreds of timeouts when the infra it needs isn't reachable.

Two things this deliberately does NOT do:

1. It does not reinvent baseline execution. `BaselineRunner.run_baselines`
   (ALWAYS_LOCAL / ALWAYS_CLOUD / STATIC_RULE / AMOF) already exists, is
   tested, and runs through the real supervisor -- this harness feeds it real
   data, it doesn't duplicate it.

2. It does not claim a full run happened if the infra to run it isn't here.
   `preflight()` checks Ollama, the cloud runtime, the embedding backend and
   the database BEFORE spending any time, and the smoke-scale defaults below
   are sized for what this sandbox can actually execute today (see
   `implementation plan.md`'s Week 2 section for the specific measurement:
   Ollama unreachable, cloud reachable but rate-limited under sustained load).
   `--seeds 5 --sample-size 100` is the real target once genuine infra is
   available; running it here would mostly measure OpenRouter's free-tier
   rate limit, not the router.

Baseline execution needs DatasetItemSchema rows (task/category/complexity/
expected_capability/expected_execution_mode/...), and the v2 privacy corpus
was built for classifier evaluation (item/label/template_id/signal_type), not
for that shape. `_adapt_to_dataset_item()` is the seam between them: every
field the router actually cares about (task text, privacy_level) is the real
rubric-derived data; `expected_capability` is a constant
("text_generation") because none of these templates were written as
capability-routing ground truth, and that's disclosed in the report rather
than presented as a measured value. `expected_execution_mode` IS derived from
the real rubric label (public -> cloud, internal/confidential -> local) since
that is exactly this project's actual thesis and is not circular: it comes
from the rubric, not from the classifier being evaluated.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Optional

SERVICE_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = SERVICE_ROOT / "evaluation" / "datasets"
ARTIFACTS_DIR = SERVICE_ROOT / "evaluation" / "artifacts" / "harness_v2"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))


# --------------------------------------------------------------------------
# Pre-flight
# --------------------------------------------------------------------------


def preflight() -> dict[str, Any]:
    """
    Checks the four things a full run actually needs, and reports each
    separately -- "Ollama down" and "cloud rate-limited" are different facts
    that call for different next steps, so they must never be collapsed into
    one pass/fail verdict.
    """
    status: dict[str, Any] = {}

    try:
        from app.db.session import SessionLocal
        from app.models.execution import Execution

        db = SessionLocal()
        try:
            db.query(Execution).limit(1).all()
            status["database"] = True
        finally:
            db.close()
    except Exception as exc:
        status["database"] = False
        status["database_error"] = str(exc)

    try:
        from app.rag.embeddings import embedding_service

        vec = embedding_service.generate_embedding("preflight check")
        status["embeddings"] = bool(vec) and any(v != 0.0 for v in vec)
    except Exception as exc:
        status["embeddings"] = False
        status["embeddings_error"] = str(exc)

    try:
        from app.runtime.local_runtime import ollama_runtime

        status["ollama_local"] = ollama_runtime.is_available()
    except Exception as exc:
        status["ollama_local"] = False
        status["ollama_local_error"] = str(exc)

    try:
        from app.runtime.cloud_runtime import litellm_runtime

        status["cloud_litellm"] = litellm_runtime.is_available()
    except Exception as exc:
        status["cloud_litellm"] = False
        status["cloud_litellm_error"] = str(exc)

    # A concurrent-load test on 2026-09-13 found sustained 89-90% system RAM
    # and 50-60% CPU during 5-then-10 simultaneous local-inference calls, on a
    # machine with only ~1.5GB free at idle (16.9GB total). Completion rate
    # held at 100%, but per-call latency variance widened by an order of
    # magnitude under load. Logged here, every run, so a latency-variance
    # finding can be attributed to hardware headroom rather than presented as
    # an inherent property of the router -- see implementation plan.md.
    hw, hw_error = _hardware_snapshot()
    status["hardware"] = hw
    if hw_error:
        status["hardware_error"] = hw_error

    return status


def _hardware_snapshot() -> tuple[Optional[dict[str, Any]], Optional[str]]:
    try:
        import psutil

        mem = psutil.virtual_memory()
        return {
            "ram_total_gb": round(mem.total / 1e9, 1),
            "ram_available_gb": round(mem.available / 1e9, 1),
            "ram_used_pct": mem.percent,
            "cpu_logical_cores": psutil.cpu_count(logical=True),
            "cpu_used_pct": psutil.cpu_percent(interval=0.2),
        }, None
    except Exception as exc:
        return None, str(exc)


def print_preflight(status: dict[str, Any]) -> None:
    print("Pre-flight:")
    for key in ("database", "embeddings", "ollama_local", "cloud_litellm"):
        mark = "OK" if status.get(key) else "UNAVAILABLE"
        print(f"  {key:<16} {mark}")
        if not status.get(key) and status.get(f"{key}_error"):
            print(f"    -> {status[f'{key}_error']}")

    hw = status.get("hardware")
    if hw:
        print(f"  hardware         RAM {hw['ram_available_gb']:.1f}/{hw['ram_total_gb']:.1f}GB free "
              f"({hw['ram_used_pct']:.0f}% used), CPU {hw['cpu_used_pct']:.0f}% used "
              f"across {hw['cpu_logical_cores']} logical cores")
        if hw["ram_used_pct"] >= 85:
            print("    -> WARNING: low RAM headroom. Latency-variance results from this "
                  "run may reflect memory pressure, not router behavior alone.")
    else:
        print(f"  hardware         UNKNOWN -> {status.get('hardware_error')}")


# --------------------------------------------------------------------------
# Classifier + router at full scale (needs only embeddings)
# --------------------------------------------------------------------------


def run_classifier_eval(eval_path: Path, exemplars_path: Path) -> dict[str, Any]:
    from app.core.config import settings
    from app.evaluation.privacy_metrics import classify_all, load_jsonl, score
    from app.privacy.classifier import privacy_classifier

    exemplars = load_jsonl(exemplars_path)
    privacy_classifier.load_exemplars(exemplars)

    eval_rows = load_jsonl(eval_path)
    classified = classify_all(eval_rows)
    return score(classified, settings.PRIVACY_CLOUD_CONFIDENCE)


# --------------------------------------------------------------------------
# Stratified multi-seed sampling for the baseline sweep
# --------------------------------------------------------------------------


def stratified_sample(
    rows: list[dict[str, Any]],
    n: int,
    seed: int,
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    by_label: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_label.setdefault(r["label"], []).append(r)

    per_label = max(1, n // len(by_label))
    sample: list[dict[str, Any]] = []
    for label, items in by_label.items():
        pool = items[:]
        rng.shuffle(pool)
        sample.extend(pool[:per_label])
    rng.shuffle(sample)
    return sample[:n]


def _adapt_to_dataset_item(row: dict[str, Any]):
    """See module docstring for exactly what is and isn't rubric-derived here."""
    from app.evaluation.schemas import DatasetItemSchema

    expected_mode = "cloud" if row["label"] == "public" else "local"
    return DatasetItemSchema(
        task_id=row["item_id"],
        task=row["text"],
        category=row.get("signal_type", "privacy_eval"),
        complexity="medium",
        privacy_level=row["label"],
        expected_capability="text_generation",  # constant -- see module docstring
        expected_execution_mode=expected_mode,  # derived from the rubric label
        expected_approval_requirement=False,
    )


# --------------------------------------------------------------------------
# Uniqueness guard: the exact failure mode found in 44/46 of Week 1's
# historical artifacts (the same task, byte-identical, repeated 10x).
# --------------------------------------------------------------------------


def assert_no_fixture_duplication(results: list[Any], context: str) -> None:
    task_ids = [r.task_id for r in results]
    if len(task_ids) != len(set(task_ids)):
        dupes = [t for t, c in Counter(task_ids).items() if c > 1]
        raise AssertionError(f"{context}: duplicate task_id in one run: {dupes}")

    latencies = {r.latency_ms for r in results if getattr(r, "latency_ms", None) is not None}
    if len(results) > 3 and len(latencies) <= 1:
        raise AssertionError(
            f"{context}: every result has the same latency ({latencies}) -- "
            "this is the exact fixture-duplication pattern that corrupted "
            "44/46 of Week 1's historical artifacts. Refusing to report this "
            "as a real run."
        )


# --------------------------------------------------------------------------
# Baseline sweep across seeds
# --------------------------------------------------------------------------


def run_baseline_seed(seed: int, sample_size: int, eval_rows: list[dict[str, Any]]) -> dict[str, Any]:
    from app.db.session import SessionLocal
    from app.evaluation.baselines import BaselineRunner
    from app.evaluation.schemas import EvaluationConfigSchema

    sample = stratified_sample(eval_rows, sample_size, seed)
    items = [_adapt_to_dataset_item(r) for r in sample]

    # cache_enabled defaults True on EvaluationConfigSchema. Left on, the 4
    # baselines run sequentially against the SAME items within a seed, and
    # the same DB/cache persists across all 5 seeds -- AMOF's routing
    # decision for a public item is "cloud", the same mode ALWAYS_CLOUD just
    # used on that identical text moments earlier, so AMOF would get a free
    # cache hit paid for by a baseline that ran first. By seed 1+ nearly
    # everything would be cache-warm from seed 0, collapsing the intended
    # 5-seed variance for reasons that have nothing to do with the router.
    # Forced off here so every call is a genuine, comparable, fresh
    # inference; cache's own effect is measured separately by the ablation
    # study's CACHE_ON/CACHE_OFF arms, not conflated into this comparison.
    config = EvaluationConfigSchema(dataset_version="privacy_corpus_v2", seed=seed, cache_enabled=False)

    # preflight() only runs once, before the seed loop -- too coarse for a
    # multi-hour sweep where hardware headroom can drift between seed 0 and
    # seed 4. Snapshotting before/after each seed catches that drift per run,
    # not just at sweep start.
    hw_before, hw_before_err = _hardware_snapshot()

    db = SessionLocal()
    started = time.time()
    try:
        baseline_metrics = BaselineRunner.run_baselines(db=db, tasks=items, config=config)
    finally:
        db.close()
    elapsed = round(time.time() - started, 2)

    hw_after, hw_after_err = _hardware_snapshot()

    return {
        "seed": seed,
        "sample_size": len(items),
        "elapsed_s": elapsed,
        "hardware_before": hw_before or {"error": hw_before_err},
        "hardware_after": hw_after or {"error": hw_after_err},
        "baselines": [b.model_dump() for b in baseline_metrics],
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--eval", type=Path, default=DATASETS_DIR / "privacy_eval_v2.jsonl")
    parser.add_argument("--exemplars", type=Path, default=DATASETS_DIR / "privacy_exemplars_v2.jsonl")
    parser.add_argument("--seeds", type=int, default=1,
                         help="Independent stratified samples for the baseline sweep. "
                              "Real target is 5; default is 1 (smoke scale) -- see module docstring.")
    parser.add_argument("--sample-size", type=int, default=9,
                         help="Items per seed for the baseline sweep. Real target is 100; "
                              "default is 9 (3 per label, smoke scale).")
    parser.add_argument("--skip-baselines", action="store_true",
                         help="Run only the classifier+router eval (needs no generation infra).")
    parser.add_argument("--force", action="store_true",
                         help="Run baselines even if pre-flight finds no usable generation backend.")
    parser.add_argument("--run-tag", type=str, default=None,
                         help="Identifies this run's checkpoint files (evaluation/artifacts/"
                              "harness_v2/checkpoint_<tag>_seed<N>.json), written as each seed "
                              "completes. Defaults to a fresh timestamp. Pass the SAME tag with "
                              "--resume to pick a killed run back up.")
    parser.add_argument("--resume", action="store_true",
                         help="Skip seeds that already have a checkpoint file under --run-tag "
                              "and load their results from disk instead of recomputing them. "
                              "Requires --run-tag to match the killed run's tag (printed at that "
                              "run's start and on every seed's checkpoint line).")
    args = parser.parse_args(argv)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    run_tag = args.run_tag or str(int(time.time()))
    print(f"run_tag: {run_tag}  (pass --run-tag {run_tag} --resume to pick this run back up if it dies)")

    status = preflight()
    print_preflight(status)

    report: dict[str, Any] = {"preflight": status}

    print("\n--- Classifier + router (full scale; needs only embeddings) ---")
    if status.get("embeddings"):
        classifier_result = run_classifier_eval(args.eval, args.exemplars)
        report["classifier"] = classifier_result
        print(f"n={classifier_result['n']} accuracy={classifier_result['accuracy']:.3f} "
              f"leak_rate={classifier_result['safety']['leak_rate']:.3f} "
              f"over_restriction={classifier_result['safety']['over_restriction_rate']:.3f}")
    else:
        print("SKIPPED: embedding backend unreachable. Nothing to fake here -- "
              "fix the embedding backend (OPENROUTER_API_KEY or a local "
              "nomic-embed-text) and re-run.")
        report["classifier"] = None

    print("\n--- Baseline sweep (needs a reachable generation backend) ---")
    can_generate = status.get("ollama_local") or status.get("cloud_litellm")
    if args.skip_baselines:
        print("SKIPPED: --skip-baselines.")
        report["baselines"] = None
    elif not can_generate and not args.force:
        print("SKIPPED: neither Ollama nor the cloud runtime is reachable. "
              "Nothing here would measure the router -- it would measure how "
              "fast this environment can generate connection-refused errors. "
              "Pass --force to run anyway (results will show it), or fix "
              "infra and re-run with --seeds 5 --sample-size 100 for the real "
              "target scale.")
        report["baselines"] = None
    else:
        eval_rows = json.loads(
            "[" + ",".join(l for l in args.eval.read_text(encoding="utf-8").splitlines() if l.strip()) + "]"
        )
        seed_reports = []
        for seed in range(args.seeds):
            checkpoint_path = ARTIFACTS_DIR / f"checkpoint_{run_tag}_seed{seed}.json"

            if args.resume and checkpoint_path.exists():
                seed_report = json.loads(checkpoint_path.read_text(encoding="utf-8"))
                print(f"\nSeed {seed}: RESUMED from {checkpoint_path} (not recomputed)")
            else:
                print(f"\nSeed {seed}: sampling {args.sample_size} items, running 4 baselines "
                      f"through the real supervisor...")
                seed_report = run_baseline_seed(seed, args.sample_size, eval_rows)
                print(f"  done in {seed_report['elapsed_s']}s")
                # Written immediately, not just held in memory for the final
                # report at the end of the whole sweep -- a killed process
                # (laptop closed, session interrupted) previously lost every
                # completed seed because main() only wrote output once, after
                # the entire seed loop finished. Each seed's own result is
                # now durable the moment that seed finishes.
                checkpoint_path.write_text(json.dumps(seed_report, indent=2, default=str), encoding="utf-8")
                print(f"  checkpoint written: {checkpoint_path}")

            for b in seed_report["baselines"]:
                print(f"  {b['baseline_name']:<14} completion={b['completion_rate']:.2f} "
                      f"routing_acc={b['routing_accuracy']:.2f} "
                      f"privacy_leak={b['privacy_leak_rate']:.2f} "
                      f"p95_latency_ms={b['p95_latency_ms']:.0f}")
            seed_reports.append(seed_report)
        report["baselines"] = seed_reports
        report["run_tag"] = run_tag

        if not can_generate:
            print("\nNOTE: this ran with --force despite no reachable generation "
                  "backend. High completion failure rates below reflect that, "
                  "not a router defect -- see preflight above.")

    out_path = ARTIFACTS_DIR / f"harness_v2_report_{int(time.time())}.json"
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"\nWrote {out_path}")
    print("\nFull-scale command once infra is available:")
    print("  python -m app.evaluation.harness_v2 --seeds 5 --sample-size 100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
