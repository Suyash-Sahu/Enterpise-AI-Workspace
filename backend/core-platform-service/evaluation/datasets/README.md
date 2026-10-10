# AMOF Evaluation Datasets

This directory contains versioned evaluation datasets for Project 10: AMOF Research Evaluation & Benchmarking System.

## Dataset Standard
Each dataset file is formatted in JSON Lines (`.jsonl`) format.

### Fields per JSONL item:
- `task_id` (string): Unique task identifier (e.g., `task_001`).
- `task` (string): Prompt / query string passed to the AMOF pipeline.
- `category` (string): Task category (`document_summary`, `rag_search`, `rag_answer`, `database_query`, `text_generation`, `communication_action`). `calendar_action` was removed (Phase 10, 2026-09-20): its capability has no registered `ExecutionHandler`, so any such task is guaranteed to fail regardless of routing.
- `complexity` (string): Task complexity rating (`simple`, `medium`, `complex`).
- `privacy_level` (string): Data sensitivity level (`public`, `internal`, `confidential`, `restricted`). `restricted` added (Phase 12, 2026-09-20) — see `app/privacy/contracts.py::SensitivityLabel.RESTRICTED`.
- `expected_capability` (string): Ground-truth target capability.
- `expected_execution_mode` (string): Ground-truth target execution routing (`local` or `cloud`) -- a prediction of live router behavior in `auto` mode, not a human label; see `docs/research/evaluation-methodology.md`'s "Provenance" subsection for how it must be derived.
- `expected_approval_requirement` (boolean): Whether Human-In-The-Loop approval is required.
- `expected_answer` (string): Ground-truth answer criteria or expected keywords.
- `metadata` (object, optional): Free-form task annotations, e.g. `design` (`tier_coverage` / `adversarial_boundary` / `restricted_hard_filter`) and `provenance` (how the expected fields were derived). See `amof_eval_v2.jsonl`.

## Dataset versions
- `amof_eval_v1.jsonl` (9 tasks): original benchmark. Kept unchanged for historical comparison.
- `amof_eval_v2.jsonl` (20 tasks, Phase 12): expanded privacy-tier x task-type benchmark with full RESTRICTED coverage and 2 adversarial/boundary cases. Use this for new evaluation runs; see `docs/research/evaluation-methodology.md`.

## Reproducibility & Integrity
Every evaluation run computes the SHA-256 hash of the target dataset file and persists `dataset_version` and `dataset_hash` alongside execution traces. Coverage balance (privacy-tier x category) can be checked at any time via `DatasetValidator.coverage_report(items)`.
