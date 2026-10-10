"""
ReconcilerAgent (Phase 23): cross-source merge, dedupe and contradiction
detection over other agents' outputs.

Tools: none -- a pure function, deliberately. It never calls a service or
connector; it only reasons over the (key, value, source) items its caller
already collected from other agents' AgentResults.

Merge rule: items are grouped by `key` (normalized: stripped, lowercased).
- One distinct value across all sources with that key -> merged, sources listed.
- More than one distinct value for the same key -> a contradiction (not
  silently resolved by picking one, since that would fabricate agreement
  that was never measured).
- Two items with the same key AND the same value from different sources are
  a duplicate, not a contradiction -- corroboration, not conflict.
"""
from collections import defaultdict
from typing import Any

from pydantic import BaseModel, Field

from app.agents.base import Agent, AgentContext, AgentResult, AgentSpec


class ReconcileItem(BaseModel):
    key: str
    value: Any
    source: str


class ReconcileInput(BaseModel):
    items: list[ReconcileItem] = Field(default_factory=list)


class Reconciliation(BaseModel):
    merged: list[dict] = Field(default_factory=list)
    duplicates: list[dict] = Field(default_factory=list)
    contradictions: list[dict] = Field(default_factory=list)


def _norm(key: str) -> str:
    return key.strip().lower()


class ReconcilerAgent(Agent):
    spec = AgentSpec(
        name="ReconcilerAgent",
        role="cross-source merge, dedupe and contradiction detection",
        input_schema=ReconcileInput,
        output_schema=Reconciliation,
        tools=[],
        reads_state=[],
        writes_state=[],
        side_effect="read_only",
        requires_human_approval=False,
        verifier="ReconciliationVerifier",
    )

    def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
        assert isinstance(inputs, ReconcileInput)
        by_key: dict[str, list[ReconcileItem]] = defaultdict(list)
        for item in inputs.items:
            by_key[_norm(item.key)].append(item)

        merged: list[dict] = []
        duplicates: list[dict] = []
        contradictions: list[dict] = []

        for key, items in by_key.items():
            distinct_values = {}
            for item in items:
                value_key = repr(item.value)
                distinct_values.setdefault(value_key, {"value": item.value, "sources": []})
                distinct_values[value_key]["sources"].append(item.source)

            if len(distinct_values) == 1:
                only = next(iter(distinct_values.values()))
                merged.append({"key": key, "value": only["value"], "sources": only["sources"]})
                if len(only["sources"]) > 1:
                    duplicates.append({"key": key, "value": only["value"], "sources": only["sources"]})
            else:
                contradictions.append({
                    "key": key,
                    "candidates": [
                        {"value": v["value"], "sources": v["sources"]}
                        for v in distinct_values.values()
                    ],
                })

        result = Reconciliation(merged=merged, duplicates=duplicates, contradictions=contradictions)
        return AgentResult(
            output=result,
            evidence=[i.source for i in inputs.items],
            notes=f"{len(merged)} merged, {len(duplicates)} duplicate groups, {len(contradictions)} contradictions",
        )


reconciler_agent = ReconcilerAgent()
