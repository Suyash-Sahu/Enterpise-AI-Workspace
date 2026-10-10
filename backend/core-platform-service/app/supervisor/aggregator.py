"""
Phase 32: Typed aggregation replacing plain concatenation.

The original ResultAggregator concatenated step outputs and dropped provenance.
This updated version produces a typed, provenance-preserving merge using the
Phase 32 coordination patterns (fan_in_aggregate). Single-source runs are
unchanged: when only one step contributes, union degenerates to that step's
items with its source_step_id attached.
"""
import logging
from typing import Any
from app.schemas.supervisor import PlanStep
from app.supervisor.coordination import fan_in_aggregate, MergeStrategy

logger = logging.getLogger(__name__)


class ResultAggregator:

    def aggregate(self, steps: list[PlanStep]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        Aggregates outputs from completed DAG steps.
        Returns tuple of (aggregated_context_dict, sources_citations_list).

        Phase 32: each step's output is individually tracked with its source
        step_id so provenance survives the merge. Single-source runs produce
        exactly the same context_data shape as before (regression-safe).
        """
        context_data: dict[str, Any] = {}
        sources: list[dict[str, Any]] = []
        fan_in_inputs: dict[str, list[Any]] = {}

        for step in steps:
            if step.status != "COMPLETED" or not step.result:
                continue

            res = step.result.get("result", step.result)

            # Extract Citations from P3 RAG Search/Answer
            if isinstance(res, dict):
                if "citations" in res and isinstance(res["citations"], list):
                    for cit in res["citations"]:
                        sources.append({**cit, "_source_step_id": step.step_id})
                elif "results" in res and isinstance(res["results"], list):
                    for item in res["results"]:
                        sources.append({
                            "document_id": item.get("document_id"),
                            "source": item.get("source"),
                            "score": item.get("score"),
                            "content": item.get("content", "")[:200],
                            "_source_step_id": step.step_id,
                        })

                # Extract database query summary from P4
                if "sql" in res and "rows" in res:
                    sources.append({
                        "type": "database_query",
                        "sql": res.get("sql"),
                        "row_count": res.get("row_count", len(res.get("rows", []))),
                        "_source_step_id": step.step_id,
                    })

            # Phase 32: collect for fan-in
            items = res if isinstance(res, list) else [res]
            fan_in_inputs[step.step_id] = items

            context_data[step.step_id] = {
                "capability": step.capability,
                "output": res,
            }

        # Phase 32: run typed fan-in aggregation when more than one source contributed
        if len(fan_in_inputs) > 1:
            try:
                fan_result = fan_in_aggregate(fan_in_inputs, strategy=MergeStrategy.UNION)
                context_data["_fan_in_audit"] = fan_result.audit_record
                context_data["_source_step_ids"] = fan_result.source_step_ids
            except Exception as exc:
                logger.warning("[P32 Aggregator]: fan_in_aggregate raised: %s", exc)

        return context_data, sources


result_aggregator = ResultAggregator()
