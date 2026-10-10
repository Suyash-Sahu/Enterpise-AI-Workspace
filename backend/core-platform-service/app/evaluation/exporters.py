import csv
import io
import os
from typing import Dict, Any, List
from sqlalchemy.orm import Session

from app.models.evaluation import EvaluationRun, EvaluationResult, EvaluationMetric, EvaluationTask


class EvaluationExporter:
    """
    Exports evaluation run artifacts into standardized CSV and JSON research formats.
    """

    @classmethod
    def export_csv(cls, db: Session, run_id: str) -> str:
        results = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.run_id == run_id)
            .order_by(EvaluationResult.id.asc())
            .all()
        )
        tasks_map = {
            t.task_id: t
            for t in db.query(EvaluationTask).filter(EvaluationTask.run_id == run_id).all()
        }

        output = io.StringIO()
        fieldnames = [
            "run_id",
            "task_id",
            "category",
            "complexity",
            # Ground truth from the dataset, and the classifier's prediction,
            # as two separate columns. They used to share one: when the task
            # lookup missed, the prediction was written into the privacy_level
            # column, so an analysis comparing them could silently compare a
            # value against itself.
            "privacy_level",
            "privacy_predicted",
            "privacy_confidence",
            "expected_capability",
            "expected_execution_mode",
            "actual_capability",
            "capability_correct",
            "actual_execution_mode",
            "actual_model",
            "routing_correct",
            "latency_ms",
            "input_tokens",
            "output_tokens",
            "total_tokens",
            "estimated_cost",
            "cache_hit",
            "approval_required",
            "approval_status",
            "verification_status",
            "completion_success",
            "error_type",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            task = tasks_map.get(r.task_id)
            writer.writerow({
                "run_id": r.run_id,
                "task_id": r.task_id,
                "category": task.category if task else "",
                "complexity": task.complexity if task else "",
                "privacy_level": task.privacy_level if task else "",
                "privacy_predicted": r.privacy_classification,
                "privacy_confidence": r.privacy_confidence,
                "expected_capability": task.expected_capability if task else "",
                "expected_execution_mode": task.expected_execution_mode if task else "",
                "actual_capability": r.actual_capability,
                "capability_correct": r.capability_correct,
                "actual_execution_mode": r.actual_execution_mode,
                "actual_model": r.actual_model,
                "routing_correct": r.routing_correct,
                "latency_ms": r.latency_ms,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "total_tokens": r.total_tokens,
                "estimated_cost": r.estimated_cost,
                "cache_hit": r.cache_hit,
                "approval_required": r.approval_required,
                "approval_status": r.approval_status,
                "verification_status": r.verification_status,
                "completion_success": r.completion_success,
                "error_type": r.error_type or "",
            })

        return output.getvalue()

    @classmethod
    def export_json(cls, db: Session, run_id: str) -> Dict[str, Any]:
        run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
        if not run:
            return {}

        results = db.query(EvaluationResult).filter(EvaluationResult.run_id == run_id).all()
        metrics = db.query(EvaluationMetric).filter(EvaluationMetric.run_id == run_id).all()

        return {
            "run_id": run.run_id,
            "status": run.status,
            "dataset_version": run.dataset_version,
            "dataset_hash": run.dataset_hash,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "task_count": run.task_count,
            "completed_count": run.completed_count,
            "failed_count": run.failed_count,
            "configuration": run.configuration_json,
            "git_commit": run.git_commit,
            "metrics": [
                {
                    "metric_name": m.metric_name,
                    "metric_value": m.metric_value,
                    "denominator": m.denominator,
                    "numerator": m.numerator,
                    "metadata": m.metric_metadata,
                }
                for m in metrics
            ],
            "item_results": [
                {
                    "task_id": r.task_id,
                    "status": r.status,
                    "actual_capability": r.actual_capability,
                    "capability_correct": r.capability_correct,
                    "actual_execution_mode": r.actual_execution_mode,
                    "actual_model": r.actual_model,
                    "routing_correct": r.routing_correct,
                    "approval_required": r.approval_required,
                    "approval_status": r.approval_status,
                    "cache_hit": r.cache_hit,
                    "verification_status": r.verification_status,
                    "latency_ms": r.latency_ms,
                    "input_tokens": r.input_tokens,
                    "output_tokens": r.output_tokens,
                    "total_tokens": r.total_tokens,
                    "estimated_cost": r.estimated_cost,
                    "privacy_classification": r.privacy_classification,
                    "privacy_confidence": r.privacy_confidence,
                    "output_quality_score": r.output_quality_score,
                    "completion_success": r.completion_success,
                    "error_type": r.error_type,
                    "error_message": r.error_message,
                    "trace_json": r.trace_json,
                }
                for r in results
            ],
        }

    @classmethod
    def export_charts(cls, db: Session, run_id: str, output_dir: str) -> Dict[str, str]:
        """
        Renders real per-run charts from data actually persisted for this
        run: EvaluationResult/Metric rows, and baselines/ablations (which
        live inside EvaluationRun.configuration_json -- there is no separate
        EvaluationBaseline/EvaluationAblation table, see
        runner.py::start_run's comment on why they're stored there).

        Writes PNGs under `output_dir` (the caller passes a `charts/`
        subdirectory of the run's artifact folder, kept separate from the
        raw JSON/CSV siblings per Phase 14's requirement). Returns
        {chart_name: file_path} for whichever charts had real data; a chart
        with no underlying data is omitted, not rendered empty.
        """
        import matplotlib
        matplotlib.use("Agg")  # no display in this process; must never try to open one
        import matplotlib.pyplot as plt

        run = db.query(EvaluationRun).filter(EvaluationRun.run_id == run_id).first()
        results = (
            db.query(EvaluationResult)
            .filter(EvaluationResult.run_id == run_id)
            .order_by(EvaluationResult.id.asc())
            .all()
        )
        metrics = db.query(EvaluationMetric).filter(EvaluationMetric.run_id == run_id).all()
        tasks_map = {
            t.task_id: t
            for t in db.query(EvaluationTask).filter(EvaluationTask.run_id == run_id).all()
        }

        os.makedirs(output_dir, exist_ok=True)
        charts: Dict[str, str] = {}

        # Chart 1: metric summary bar chart, from real AVAILABLE metrics only.
        available = [m for m in metrics if m.metric_value is not None]
        if available:
            fig, ax = plt.subplots(figsize=(8, 4.5))
            names = [m.metric_name for m in available]
            values = [m.metric_value for m in available]
            ax.bar(names, values, color="#0891b2")
            ax.set_ylabel("Value")
            ax.set_title(f"Evaluation Metrics -- run {run_id[:12]}")
            ax.tick_params(axis="x", rotation=45)
            fig.tight_layout()
            path = os.path.join(output_dir, "metrics_summary.png")
            fig.savefig(path, dpi=150)
            plt.close(fig)
            charts["metrics_summary"] = path

        # Chart 2: latency distribution histogram, from real measured latencies.
        latencies: List[float] = [r.latency_ms for r in results if r.latency_ms is not None]
        if latencies:
            fig, ax = plt.subplots(figsize=(8, 4.5))
            ax.hist(latencies, bins=min(20, max(5, len(latencies) // 2)), color="#6366f1", edgecolor="white")
            ax.set_xlabel("Latency (ms)")
            ax.set_ylabel("Task count")
            ax.set_title(f"Latency Distribution -- run {run_id[:12]} (n={len(latencies)})")
            fig.tight_layout()
            path = os.path.join(output_dir, "latency_distribution.png")
            fig.savefig(path, dpi=150)
            plt.close(fig)
            charts["latency_distribution"] = path

        # Chart 3: completion rate by task category, from real per-item results.
        by_category: Dict[str, List[bool]] = {}
        for r in results:
            task = tasks_map.get(r.task_id)
            if task and r.completion_success is not None:
                by_category.setdefault(task.category, []).append(bool(r.completion_success))
        if by_category:
            fig, ax = plt.subplots(figsize=(8, 4.5))
            categories = sorted(by_category.keys())
            rates = [sum(by_category[c]) / len(by_category[c]) for c in categories]
            ax.bar(categories, rates, color="#059669")
            ax.set_ylim(0, 1.0)
            ax.set_ylabel("Completion rate")
            ax.set_title(f"Completion Rate by Category -- run {run_id[:12]}")
            ax.tick_params(axis="x", rotation=30)
            fig.tight_layout()
            path = os.path.join(output_dir, "completion_by_category.png")
            fig.savefig(path, dpi=150)
            plt.close(fig)
            charts["completion_by_category"] = path

        # Chart 4: baseline strategy comparison, from the baselines this run
        # actually computed (persisted in configuration_json -- see
        # runner.py::start_run). Omitted, not empty, when a run has none
        # (run_baselines=False).
        baselines = ((run.configuration_json or {}).get("baselines") or []) if run else []
        if baselines:
            fig, ax = plt.subplots(figsize=(8, 4.5))
            names = [b.get("baseline_name", "?") for b in baselines]
            values = [b.get("routing_accuracy", 0.0) or 0.0 for b in baselines]
            colors = ["#0891b2" if "AMOF" in n.upper() else "#64748b" for n in names]
            ax.bar(names, values, color=colors)
            ax.set_ylim(0, 1.0)
            ax.set_ylabel("Routing accuracy")
            ax.set_title(f"Baseline Comparison -- run {run_id[:12]}")
            ax.tick_params(axis="x", rotation=20)
            fig.tight_layout()
            path = os.path.join(output_dir, "baseline_comparison.png")
            fig.savefig(path, dpi=150)
            plt.close(fig)
            charts["baseline_comparison"] = path

        return charts
