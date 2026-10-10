"""
Precision/recall harness for the privacy classifier, plus a threshold sweep.

Run it:

    python -m app.evaluation.privacy_metrics
    python -m app.evaluation.privacy_metrics --no-exemplars   # rules only
    python -m app.evaluation.privacy_metrics --sweep

Two numbers matter more than accuracy, and they are reported separately
because they trade against each other:

  leak_rate
      Fraction of genuinely sensitive items (true label internal or
      confidential) that the system would have permitted to leave the machine.
      This is the safety metric. Its target is zero, and a design that trades
      any leak for throughput has misunderstood the problem.

  over_restriction_rate
      Fraction of genuinely public items kept local anyway. This is the *cost*
      of safety: wasted cloud capability, higher latency, and in a cost
      comparison it is what stops the privacy claim from being free.

Reporting only accuracy hides both. A classifier that answers CONFIDENTIAL to
everything scores 0% leak and looks perfect until you notice it also scores
100% over-restriction and has reduced the router to always-local, which is
exactly the failure the earlier version of this system had.

Train/test separation: exemplars come from privacy_exemplars_v1.jsonl and the
evaluation set from privacy_eval_v1.jsonl. These files must stay disjoint. A
k-NN scored on its own exemplars reports 100% and means nothing; the harness
checks for overlap and refuses to run if it finds any.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Optional

from app.core.config import settings
from app.privacy.classifier import privacy_classifier
from app.privacy.contracts import SensitivityLabel

LABELS = [lab.value for lab in SensitivityLabel]
# AMOF-X Phase 3: RESTRICTED (live credentials) is strictly more sensitive
# than CONFIDENTIAL and must count toward leak_rate too -- the corpus does
# not yet label anything RESTRICTED (see CURRENT_STATE.md), but if it ever
# does, silently excluding it here would hide exactly the leak this metric
# exists to catch.
SENSITIVE = {
    SensitivityLabel.INTERNAL.value,
    SensitivityLabel.CONFIDENTIAL.value,
    SensitivityLabel.RESTRICTED.value,
}

SERVICE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVAL = SERVICE_ROOT / "evaluation" / "datasets" / "privacy_eval_v1.jsonl"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def per_class_scores(pairs: Iterable[tuple[str, str]]) -> dict[str, dict[str, float]]:
    """
    pairs: (true_label, predicted_label). Returns precision/recall/F1/support
    per class, computed directly so the harness carries no sklearn dependency.
    """
    pairs = list(pairs)
    out: dict[str, dict[str, float]] = {}
    for label in LABELS:
        tp = sum(1 for t, p in pairs if t == label and p == label)
        fp = sum(1 for t, p in pairs if t != label and p == label)
        fn = sum(1 for t, p in pairs if t == label and p != label)
        precision = tp / (tp + fp) if (tp + fp) else 0.0
        recall = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0
        out[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": float(tp + fn),
        }
    return out


def safety_scores(rows: list[dict[str, Any]]) -> dict[str, float]:
    """
    Leak and over-restriction, computed from what the router would actually
    permit rather than from the label alone. `cloud_allowed` is the real
    decision: a PUBLIC prediction that did not clear the confidence gate still
    stays local and is therefore not a leak.
    """
    sensitive = [r for r in rows if r["true"] in SENSITIVE]
    public = [r for r in rows if r["true"] == SensitivityLabel.PUBLIC.value]

    leaked = sum(1 for r in sensitive if r["cloud_allowed"])
    restricted = sum(1 for r in public if not r["cloud_allowed"])

    return {
        "leak_rate": leaked / len(sensitive) if sensitive else 0.0,
        "leaked_count": float(leaked),
        "sensitive_count": float(len(sensitive)),
        "over_restriction_rate": restricted / len(public) if public else 0.0,
        "restricted_count": float(restricted),
        "public_count": float(len(public)),
    }


def classify_all(eval_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Classifies every row once.

    Separated from scoring so a threshold sweep embeds each item a single time
    instead of once per threshold. Re-classifying inside the sweep made an
    11-point sweep issue eleven times as many embedding calls for identical
    results.
    """
    from app.privacy.router import privacy_router

    rows: list[dict[str, Any]] = []
    for item in eval_rows:
        result = privacy_classifier.classify(item["text"])
        # Placement ignoring the confidence gate; the gate is applied per
        # threshold in score().
        label_permits_cloud = any(
            p.value == "cloud"
            for p in privacy_router.allowed_placements(
                ClassificationResultProxy(result)
            )
        )
        rows.append(
            {
                # v1 rows use task_id; v2 (generate_privacy_corpus.py) uses
                # item_id. Falling back keeps every misclassified row
                # traceable instead of printing a blank identifier.
                "task_id": item.get("task_id") or item.get("item_id", ""),
                "template_id": item.get("template_id", ""),
                "true": item["label"],
                "pred": result.label.value,
                "confidence": result.confidence,
                "stage": result.stage.value,
                "abstained": result.abstained,
                "label_permits_cloud": label_permits_cloud,
            }
        )
    return rows


class ClassificationResultProxy:
    """
    Presents a classification to the router with the confidence gate neutralised,
    so `allowed_placements` reports what the *label* permits. The threshold is
    then applied separately per sweep point. Without this the sweep could not
    distinguish "label forbids cloud" from "confidence too low".
    """

    def __init__(self, result):
        self._result = result
        self.label = result.label
        self.abstained = result.abstained
        self.confidence = 1.0  # neutralise the gate; score() re-applies it


def score(rows: list[dict[str, Any]], threshold: float) -> dict[str, Any]:
    """Scores pre-classified rows at one cloud-confidence threshold."""
    rows = [
        {**r, "cloud_allowed": r["label_permits_cloud"] and r["confidence"] >= threshold}
        for r in rows
    ]
    correct = sum(1 for r in rows if r["true"] == r["pred"])
    return {
        "n": len(rows),
        "accuracy": correct / len(rows) if rows else 0.0,
        "cloud_confidence_threshold": threshold,
        "per_class": per_class_scores((r["true"], r["pred"]) for r in rows),
        "safety": safety_scores(rows),
        "stage_counts": dict(Counter(r["stage"] for r in rows)),
        "confusion": {
            t: dict(Counter(r["pred"] for r in rows if r["true"] == t)) for t in LABELS
        },
        "rows": rows,
    }


def _print_report(report: dict[str, Any]) -> None:
    print(f"\nn = {report['n']}   accuracy = {report['accuracy']:.3f}")
    print(f"cloud confidence threshold = {report['cloud_confidence_threshold']:.2f}\n")

    print(f"{'class':<14}{'precision':>10}{'recall':>9}{'f1':>8}{'support':>9}")
    print("-" * 50)
    for label in LABELS:
        s = report["per_class"][label]
        print(
            f"{label:<14}{s['precision']:>10.3f}{s['recall']:>9.3f}"
            f"{s['f1']:>8.3f}{int(s['support']):>9}"
        )

    safety = report["safety"]
    print("\nSafety")
    print("-" * 50)
    print(
        f"  leak rate             {safety['leak_rate']:.3f}  "
        f"({int(safety['leaked_count'])}/{int(safety['sensitive_count'])} "
        f"sensitive items would reach cloud)"
    )
    print(
        f"  over-restriction rate {safety['over_restriction_rate']:.3f}  "
        f"({int(safety['restricted_count'])}/{int(safety['public_count'])} "
        f"public items kept local)"
    )

    print("\nDeciding stage")
    print("-" * 50)
    for stage, count in sorted(report["stage_counts"].items(), key=lambda kv: -kv[1]):
        print(f"  {stage:<18}{count}")

    print("\nConfusion (rows = true, cols = predicted)")
    print("-" * 50)
    print(f"{'':<14}" + "".join(f"{lab:>14}" for lab in LABELS))
    for true_label in LABELS:
        counts = report["confusion"][true_label]
        print(f"{true_label:<14}" + "".join(f"{counts.get(p, 0):>14}" for p in LABELS))

    misses = [r for r in report["rows"] if r["true"] != r["pred"]]
    if misses:
        print("\nMisclassified")
        print("-" * 50)
        for r in misses:
            marker = "  LEAK" if (r["true"] in SENSITIVE and r["cloud_allowed"]) else ""
            print(
                f"  {r['task_id']:<10}{r.get('template_id',''):<14}{r['true']:<14}-> {r['pred']:<14}"
                f"conf={r['confidence']:.2f} stage={r['stage']}{marker}"
            )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate the privacy classifier.")
    parser.add_argument("--eval", type=Path, default=DEFAULT_EVAL)
    parser.add_argument(
        "--exemplars",
        type=Path,
        default=SERVICE_ROOT / settings.PRIVACY_EXEMPLAR_PATH,
    )
    parser.add_argument(
        "--no-exemplars",
        action="store_true",
        help="Skip stage 2. Isolates what the deterministic rules achieve alone.",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="Sweep the cloud confidence threshold to trace the trade-off.",
    )
    parser.add_argument("--json", type=Path, help="Write the full report as JSON.")
    args = parser.parse_args(argv)

    eval_rows = load_jsonl(args.eval)

    if not args.no_exemplars and args.exemplars.exists():
        exemplars = load_jsonl(args.exemplars)

        overlap = {e["text"] for e in exemplars} & {r["text"] for r in eval_rows}
        if overlap:
            print(
                f"ERROR: {len(overlap)} items appear in both the exemplar and "
                "evaluation sets. A k-NN scored on its own exemplars reports a "
                "meaningless 100%. Make the files disjoint before running.",
                file=sys.stderr,
            )
            return 2

        loaded = privacy_classifier.load_exemplars(exemplars)
        print(f"Loaded {loaded}/{len(exemplars)} exemplars into stage 2.")
        if loaded == 0:
            print(
                "WARNING: no exemplars embedded (embedding service unavailable). "
                "Stage 2 will abstain and everything without a rule hit will "
                "fail closed to CONFIDENTIAL.",
                file=sys.stderr,
            )
    else:
        print("Stage 2 disabled: evaluating deterministic rules only.")

    # Classify once; the sweep then re-applies thresholds to these results
    # rather than re-embedding every item for each point on the curve.
    classified = classify_all(eval_rows)

    if args.sweep:
        print(f"\n{'threshold':>10}{'leak':>9}{'over-restrict':>16}{'accuracy':>10}")
        print("-" * 45)
        for threshold in [round(0.5 + 0.05 * i, 2) for i in range(11)]:
            rep = score(classified, threshold)
            print(
                f"{threshold:>10.2f}{rep['safety']['leak_rate']:>9.3f}"
                f"{rep['safety']['over_restriction_rate']:>16.3f}"
                f"{rep['accuracy']:>10.3f}"
            )
        return 0

    report = score(classified, settings.PRIVACY_CLOUD_CONFIDENCE)
    _print_report(report)

    if args.json:
        args.json.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nWrote {args.json}")

    leak = report["safety"]["leak_rate"]
    if leak > 0:
        print(f"\nFAIL: leak rate {leak:.3f} exceeds the target of 0.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
