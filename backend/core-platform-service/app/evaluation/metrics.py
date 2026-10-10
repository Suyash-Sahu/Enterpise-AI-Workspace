import math
from typing import List, Optional
from app.evaluation.schemas import EvaluationResultItemSchema, MetricSummarySchema


class MetricsEngine:
    """
    Calculates derived evaluation metrics strictly from real item-level evaluation results.
    Includes explicit metric_status (AVAILABLE, METRIC_UNAVAILABLE, INSUFFICIENT_DATA)
    and provenance metadata.
    """

    @staticmethod
    def calculate_metrics(
        results: List[EvaluationResultItemSchema],
        run_id: Optional[str] = None,
        dataset_hash: Optional[str] = None,
        configuration_hash: Optional[str] = None,
    ) -> List[MetricSummarySchema]:
        if not results:
            return []

        base_metadata = {
            "source": "evaluation_results",
            "run_id": run_id,
            "dataset_hash": dataset_hash,
            "configuration_hash": configuration_hash,
        }

        metrics: List[MetricSummarySchema] = []

        # 1. Routing Accuracy
        routing_evaluable = [r for r in results if r.routing_correct is not None]
        if routing_evaluable:
            correct_routing = sum(1 for r in routing_evaluable if r.routing_correct)
            metrics.append(
                MetricSummarySchema(
                    metric_name="routing_accuracy",
                    metric_value=round(correct_routing / len(routing_evaluable), 4),
                    numerator=float(correct_routing),
                    denominator=float(len(routing_evaluable)),
                    metric_status="AVAILABLE",
                    metric_metadata={
                        **base_metadata,
                        "formula": "correct_routing_decisions / total_routing_evaluable_tasks",
                    },
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="routing_accuracy",
                    metric_value=None,
                    numerator=None,
                    denominator=0.0,
                    metric_status="INSUFFICIENT_DATA",
                    metric_metadata={**base_metadata, "formula": "correct_routing_decisions / total_routing_evaluable_tasks"},
                )
            )

        # 1b. Capability Classification Accuracy -- independent of routing
        # accuracy above, which only measures local/cloud placement. Added
        # 2026-09-20 after a smoke evaluation found tasks whose capability
        # was misclassified entirely (e.g. a rag_answer task executed as
        # database_query) still counted as "routing_correct" because their
        # placement happened to match; this metric is what actually catches
        # that class of error.
        capability_evaluable = [r for r in results if r.capability_correct is not None]
        if capability_evaluable:
            correct_capability = sum(1 for r in capability_evaluable if r.capability_correct)
            metrics.append(
                MetricSummarySchema(
                    metric_name="capability_accuracy",
                    metric_value=round(correct_capability / len(capability_evaluable), 4),
                    numerator=float(correct_capability),
                    denominator=float(len(capability_evaluable)),
                    metric_status="AVAILABLE",
                    metric_metadata={
                        **base_metadata,
                        "formula": "correct_capability_classifications / total_capability_evaluable_tasks",
                    },
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="capability_accuracy",
                    metric_value=None,
                    numerator=None,
                    denominator=0.0,
                    metric_status="INSUFFICIENT_DATA",
                    metric_metadata={**base_metadata, "formula": "correct_capability_classifications / total_capability_evaluable_tasks"},
                )
            )

        # 2. Completion Rate
        completion_evaluable = [r for r in results if r.completion_success is not None]
        if completion_evaluable:
            successful_tasks = sum(1 for r in completion_evaluable if r.completion_success)
            metrics.append(
                MetricSummarySchema(
                    metric_name="completion_rate",
                    metric_value=round(successful_tasks / len(completion_evaluable), 4),
                    numerator=float(successful_tasks),
                    denominator=float(len(completion_evaluable)),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "formula": "successful_completed_tasks / total_executed_tasks"},
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="completion_rate",
                    metric_value=None,
                    numerator=None,
                    denominator=0.0,
                    metric_status="INSUFFICIENT_DATA",
                    metric_metadata={**base_metadata, "formula": "successful_completed_tasks / total_executed_tasks"},
                )
            )

        # 3. Latency Metrics (ms)
        latencies = [r.latency_ms for r in results if r.latency_ms is not None]
        if latencies:
            latencies_sorted = sorted(latencies)
            mean_latency = sum(latencies) / len(latencies)
            mid = len(latencies_sorted) // 2
            median_latency = (
                latencies_sorted[mid]
                if len(latencies_sorted) % 2 != 0
                else (latencies_sorted[mid - 1] + latencies_sorted[mid]) / 2
            )
            p95_idx = int(math.ceil(0.95 * len(latencies_sorted))) - 1
            p95_idx = max(0, min(p95_idx, len(latencies_sorted) - 1))
            p95_latency = latencies_sorted[p95_idx]

            metrics.append(
                MetricSummarySchema(
                    metric_name="avg_latency_ms",
                    metric_value=round(mean_latency, 2),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "median_ms": round(median_latency, 2), "formula": "mean(latency_ms)"},
                )
            )
            metrics.append(
                MetricSummarySchema(
                    metric_name="p95_latency_ms",
                    metric_value=round(p95_latency, 2),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "formula": "p95(latency_ms)"},
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="avg_latency_ms",
                    metric_value=None,
                    metric_status="INSUFFICIENT_DATA",
                    metric_metadata={**base_metadata, "formula": "mean(latency_ms)"},
                )
            )
            metrics.append(
                MetricSummarySchema(
                    metric_name="p95_latency_ms",
                    metric_value=None,
                    metric_status="INSUFFICIENT_DATA",
                    metric_metadata={**base_metadata, "formula": "p95(latency_ms)"},
                )
            )

        # 4. Cost and Tokens
        costs = [r.estimated_cost for r in results if r.estimated_cost is not None]
        tokens = [r.total_tokens for r in results if r.total_tokens is not None]

        if costs:
            metrics.append(
                MetricSummarySchema(
                    metric_name="total_cost_usd",
                    metric_value=round(sum(costs), 6),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "formula": "sum(estimated_cost)"},
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="total_cost_usd",
                    metric_value=None,
                    metric_status="METRIC_UNAVAILABLE",
                    metric_metadata={**base_metadata, "formula": "sum(estimated_cost)"},
                )
            )

        if tokens:
            metrics.append(
                MetricSummarySchema(
                    metric_name="total_tokens",
                    metric_value=float(sum(tokens)),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "formula": "sum(total_tokens)"},
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="total_tokens",
                    metric_value=None,
                    metric_status="METRIC_UNAVAILABLE",
                    metric_metadata={**base_metadata, "formula": "sum(total_tokens)"},
                )
            )

        # 5. Privacy Leakage (Confidential/Internal sent to Cloud)
        sensitive_tasks = [r for r in results if r.privacy_level in {"confidential", "internal"}]
        if sensitive_tasks:
            cloud_sensitive = sum(1 for r in sensitive_tasks if r.cloud_execution is True)
            metrics.append(
                MetricSummarySchema(
                    metric_name="privacy_leak_rate",
                    metric_value=round(cloud_sensitive / len(sensitive_tasks), 4),
                    numerator=float(cloud_sensitive),
                    denominator=float(len(sensitive_tasks)),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "formula": "sensitive_tasks_routed_to_cloud / total_sensitive_tasks"},
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="privacy_leak_rate",
                    metric_value=None,
                    numerator=None,
                    denominator=0.0,
                    metric_status="INSUFFICIENT_DATA",
                    metric_metadata={**base_metadata, "formula": "sensitive_tasks_routed_to_cloud / total_sensitive_tasks"},
                )
            )

        # 6. P8 Enforcement Rate
        unapproved_side_effects = [r for r in results if r.approval_required is True and r.approval_status != "APPROVED"]
        if unapproved_side_effects:
            blocked_count = sum(1 for r in unapproved_side_effects if r.execution_blocked is True or r.approval_guard_triggered is True)
            metrics.append(
                MetricSummarySchema(
                    metric_name="p8_enforcement_rate",
                    metric_value=round(blocked_count / len(unapproved_side_effects), 4),
                    numerator=float(blocked_count),
                    denominator=float(len(unapproved_side_effects)),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "formula": "blocked_unapproved_side_effects / total_unapproved_side_effects"},
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="p8_enforcement_rate",
                    metric_value=None,
                    numerator=None,
                    denominator=0.0,
                    metric_status="INSUFFICIENT_DATA",
                    metric_metadata={**base_metadata, "formula": "blocked_unapproved_side_effects / total_unapproved_side_effects"},
                )
            )

        # 7. Cache Hit Rate
        cache_eligible = [r for r in results if r.cache_hit is not None]
        if cache_eligible:
            cache_hits = sum(1 for r in cache_eligible if r.cache_hit is True)
            metrics.append(
                MetricSummarySchema(
                    metric_name="cache_hit_rate",
                    metric_value=round(cache_hits / len(cache_eligible), 4),
                    numerator=float(cache_hits),
                    denominator=float(len(cache_eligible)),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "formula": "cache_hits / total_cache_eligible_tasks"},
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="cache_hit_rate",
                    metric_value=None,
                    numerator=None,
                    denominator=0.0,
                    metric_status="INSUFFICIENT_DATA",
                    metric_metadata={**base_metadata, "formula": "cache_hits / total_cache_eligible_tasks"},
                )
            )

        # 8. Output Quality Score
        quality_scores = [r.output_quality_score for r in results if r.output_quality_score is not None]
        if quality_scores:
            metrics.append(
                MetricSummarySchema(
                    metric_name="output_quality_score",
                    metric_value=round(sum(quality_scores) / len(quality_scores), 4),
                    numerator=float(sum(quality_scores)),
                    denominator=float(len(quality_scores)),
                    metric_status="AVAILABLE",
                    metric_metadata={**base_metadata, "formula": "mean(output_quality_score)"},
                )
            )
        else:
            metrics.append(
                MetricSummarySchema(
                    metric_name="output_quality_score",
                    metric_value=None,
                    numerator=None,
                    denominator=0.0,
                    metric_status="METRIC_UNAVAILABLE",
                    metric_metadata={**base_metadata, "formula": "mean(output_quality_score)"},
                )
            )

        return metrics

