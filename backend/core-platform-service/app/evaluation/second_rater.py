"""
Independent second-rater pass over the ambiguous-tagged subset of the v2
privacy corpus. See evaluation/datasets/privacy_labeling_rubric.md's
"Independent second-rater protocol" section for why this exists and what it
is and is not allowed to do.

Two things keep this a genuine second opinion rather than an echo of the
first:

  1. Different prompt, different reasoning path. This module never imports
     the rubric text or app/privacy/classifier.py. It asks a plain-language
     version of the three-tier definition, worded independently, so
     agreement is not inflated by both raters reading the same instructions.
  2. Different model provider than the classifier's own stage-3 judge, which
     runs locally on Ollama. This calls the cloud model directly via
     LiteLLMRuntime, bypassing runtime_service and the privacy router
     entirely -- there is no routing decision to make here (nothing in this
     script chooses where anything executes), and every item it sees is
     Faker-generated fake data per the rubric's provenance statement, so
     there is no real content to protect by keeping this local.

Disagreements are written out, not resolved. Adjudicating them is a human
call (see the rubric), not something this script decides on its own.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

SERVICE_ROOT = Path(__file__).resolve().parents[2]
DATASETS_DIR = SERVICE_ROOT / "evaluation" / "datasets"

if str(SERVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVICE_ROOT))

LABELS = ("public", "internal", "confidential")

_RATER_PROMPT = """A company is deciding whether a piece of text is safe to send to an external cloud service. Classify it into exactly one of three categories:

- "public": Fine for anyone outside the company to read. No individual's personal information, no secrets, nothing the company would mind becoming public.
- "internal": The company would prefer this stays inside the company, but nothing here is separately regulated or tied to one person's private details in a legally sensitive way.
- "confidential": Contains something regulated or seriously sensitive -- a person's ID number, financial or health information, a password or credential, or legally privileged material.

If you genuinely can't decide between two categories, pick whichever one a cautious company lawyer would pick.

Respond with JSON only: {{"label": "<public|internal|confidential>", "reason": "<one short sentence>"}}

Text:
{text}
"""


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def rate_one(text: str) -> tuple[Optional[str], str]:
    from app.runtime.cloud_runtime import litellm_runtime
    from app.schemas.runtime import RuntimeGenerateRequest, RuntimeMode

    try:
        res = litellm_runtime.generate(
            RuntimeGenerateRequest(
                prompt=_RATER_PROMPT.format(text=text[:3000]),
                execution_mode=RuntimeMode.CLOUD,
                temperature=0.0,
                max_tokens=100,
                timeout=30.0,
            )
        )
    except Exception as exc:
        return None, f"rater call failed: {exc}"

    raw = (res.completion or "").strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None, "unparseable response"
    try:
        parsed = json.loads(match.group(0))
    except (ValueError, TypeError):
        return None, "invalid JSON in response"

    label = str(parsed.get("label", "")).strip().lower()
    if label not in LABELS:
        return None, f"rater returned unknown label {label!r}"
    return label, str(parsed.get("reason", ""))[:200]


def cohens_kappa(pairs: list[tuple[str, str]]) -> float:
    """Unweighted Cohen's kappa over the 3-class label set."""
    n = len(pairs)
    if n == 0:
        return 0.0
    observed_agree = sum(1 for a, b in pairs if a == b) / n

    p_a = {lab: sum(1 for a, _ in pairs if a == lab) / n for lab in LABELS}
    p_b = {lab: sum(1 for _, b in pairs if b == lab) / n for lab in LABELS}
    expected_agree = sum(p_a[lab] * p_b[lab] for lab in LABELS)

    if expected_agree >= 1.0:
        return 1.0 if observed_agree >= 1.0 else 0.0
    return (observed_agree - expected_agree) / (1 - expected_agree)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exemplars", type=Path, default=DATASETS_DIR / "privacy_exemplars_v2.jsonl")
    parser.add_argument("--eval", type=Path, default=DATASETS_DIR / "privacy_eval_v2.jsonl")
    parser.add_argument("--agreement-out", type=Path,
                         default=DATASETS_DIR / "privacy_corpus_v2_rater_agreement.json")
    parser.add_argument("--disagreements-out", type=Path,
                         default=DATASETS_DIR / "privacy_corpus_v2_disagreements.jsonl")
    parser.add_argument("--all", action="store_true",
                         help="Rate every item, not only ambiguous-tagged ones.")
    args = parser.parse_args(argv)

    rows: list[dict[str, Any]] = []
    for path, source in ((args.exemplars, "exemplars"), (args.eval, "eval")):
        for item in load_jsonl(path):
            if args.all or item.get("ambiguous"):
                rows.append({**item, "_source_file": source})

    if not rows:
        print("No ambiguous items found (pass --all to rate everything).")
        return 0

    print(f"Rating {len(rows)} item(s)...")
    pairs: list[tuple[str, str]] = []
    disagreements: list[dict[str, Any]] = []
    failures = 0

    for i, row in enumerate(rows, 1):
        rubric_label = row["label"]
        second_label, reason = rate_one(row["text"])
        if second_label is None:
            failures += 1
            print(f"  [{i}/{len(rows)}] {row['item_id']}: FAILED ({reason})")
            continue

        pairs.append((rubric_label, second_label))
        agree = rubric_label == second_label
        print(f"  [{i}/{len(rows)}] {row['item_id']}: rubric={rubric_label} "
              f"rater={second_label} {'OK' if agree else 'DISAGREE'}")

        if not agree:
            disagreements.append({
                "item_id": row["item_id"],
                "template_id": row.get("template_id"),
                "source_file": row["_source_file"],
                "text": row["text"],
                "rubric_label": rubric_label,
                "second_rater_label": second_label,
                "second_rater_reason": reason,
                "adjudicated": False,
            })

    n_rated = len(pairs)
    agreement_pct = (sum(1 for a, b in pairs if a == b) / n_rated) if n_rated else None
    kappa = cohens_kappa(pairs) if n_rated else None

    summary = {
        "n_items": len(rows),
        "n_rated": n_rated,
        "n_failed": failures,
        "n_disagreements": len(disagreements),
        "agreement_pct": round(agreement_pct, 4) if agreement_pct is not None else None,
        "cohens_kappa": round(kappa, 4) if kappa is not None else None,
        "note": (
            "Computed over the ambiguous-tagged subset only unless --all was "
            "passed. Disagreements are unresolved until manually adjudicated "
            "-- see privacy_corpus_v2_disagreements.jsonl."
        ),
    }

    args.agreement_out.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    with open(args.disagreements_out, "w", encoding="utf-8") as fh:
        for d in disagreements:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")

    print(f"\nn_rated={n_rated}  agreement={summary['agreement_pct']}  "
          f"kappa={summary['cohens_kappa']}  disagreements={len(disagreements)}")
    print(f"Wrote {args.agreement_out}")
    print(f"Wrote {args.disagreements_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
