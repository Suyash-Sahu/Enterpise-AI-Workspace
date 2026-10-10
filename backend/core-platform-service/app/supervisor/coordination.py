"""
Phase 32: Agent Coordination Patterns.

Three coordination behaviors required beyond a plain DAG:
  1. Fan-out/fan-in aggregation: typed merge with provenance retention
  2. Contradiction resolution: incompatible fact handling with precedence policy
  3. Bounded iterative refinement: one narrowing round per edge, hard-capped

Each coordination decision gets an audit record. Coordination cannot introduce
cycles. Refinement is a bounded re-invocation, not a new edge.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fan-in merge strategies
# ---------------------------------------------------------------------------

class MergeStrategy(str, Enum):
    UNION = "union"           # Combine all items (deduplicated by identity)
    INTERSECTION = "intersection"  # Keep only items present in every branch
    RANKED_MERGE = "ranked_merge"  # Rank by confidence and keep top-N


@dataclass
class ProvenancedItem:
    """A data item with the step_id it came from, so provenance survives merges."""
    value: Any
    source_step_id: str
    confidence: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "source_step_id": self.source_step_id,
            "confidence": self.confidence,
        }


@dataclass
class FanInResult:
    """The merged output of a fan-in join node."""
    items: list[ProvenancedItem]
    strategy: str
    source_step_ids: list[str]
    audit_record: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "items": [i.to_dict() for i in self.items],
            "strategy": self.strategy,
            "source_step_ids": self.source_step_ids,
            "audit_record": self.audit_record,
        }


def fan_in_aggregate(
    inputs: dict[str, list[Any]],   # step_id -> list of output items
    strategy: MergeStrategy = MergeStrategy.UNION,
    top_n: int = 10,
) -> FanInResult:
    """
    Aggregate a list of upstream step outputs using the declared strategy.

    Provenance is preserved: every merged item keeps the step_id it came from.
    """
    all_items: list[ProvenancedItem] = []
    for step_id, items in inputs.items():
        for item in (items if isinstance(items, list) else [items]):
            all_items.append(ProvenancedItem(value=item, source_step_id=step_id))

    if strategy == MergeStrategy.UNION:
        merged = _union_merge(all_items)
    elif strategy == MergeStrategy.INTERSECTION:
        merged = _intersection_merge(all_items, list(inputs.keys()))
    elif strategy == MergeStrategy.RANKED_MERGE:
        merged = _ranked_merge(all_items, top_n)
    else:
        merged = all_items

    audit = {
        "strategy": strategy.value,
        "input_step_count": len(inputs),
        "input_item_count": len(all_items),
        "merged_item_count": len(merged),
    }
    logger.debug("[Coordination] fan_in_aggregate: %s", audit)

    return FanInResult(
        items=merged,
        strategy=strategy.value,
        source_step_ids=list(inputs.keys()),
        audit_record=audit,
    )


def _union_merge(items: list[ProvenancedItem]) -> list[ProvenancedItem]:
    """Union: all items, deduplicated by value identity."""
    seen: set[int] = set()
    result: list[ProvenancedItem] = []
    for item in items:
        vid = id(item.value) if not isinstance(item.value, (str, int, float)) else item.value
        if vid not in seen:
            seen.add(vid if isinstance(vid, int) else hash(str(vid)))
            result.append(item)
    return result


def _intersection_merge(
    items: list[ProvenancedItem],
    step_ids: list[str],
) -> list[ProvenancedItem]:
    """Intersection: only items whose value appears in every upstream branch."""
    if len(step_ids) <= 1:
        return items
    # Group values by step_id
    by_step: dict[str, set] = {}
    item_map: dict[str, ProvenancedItem] = {}
    for item in items:
        key = str(item.value)
        by_step.setdefault(item.source_step_id, set()).add(key)
        item_map[key] = item
    # Intersect all branches
    common_keys = set.intersection(*(by_step.get(sid, set()) for sid in step_ids))
    return [item_map[k] for k in common_keys]


def _ranked_merge(items: list[ProvenancedItem], top_n: int) -> list[ProvenancedItem]:
    """Ranked: sort by confidence descending and return top-N."""
    ranked = sorted(items, key=lambda i: (i.confidence or 0.0), reverse=True)
    return ranked[:top_n]


# ---------------------------------------------------------------------------
# Contradiction resolution
# ---------------------------------------------------------------------------

class PrecedencePolicy(str, Enum):
    """
    Declared precedence between content sources.
    Higher index = higher precedence when sources disagree.
    """
    # user-confirmed facts beat inferred ones
    USER_CONFIRMED_BEATS_INFERRED = "user_confirmed_beats_inferred"
    # database records beat email-inferred commitments
    DB_BEATS_EMAIL = "db_beats_email"
    # most recent beats older
    MOST_RECENT = "most_recent"
    # no resolution: surface both to user
    REPORT_BOTH = "report_both"


@dataclass
class Contradiction:
    """A recorded conflict between two agents' claims about the same entity."""
    entity: str
    claim_a: Any
    source_a: str  # step_id
    claim_b: Any
    source_b: str  # step_id
    resolved_value: Optional[Any]     # None if unresolvable
    resolution: str                   # how it was resolved or "unresolvable"
    policy_applied: str

    def to_dict(self) -> dict:
        return {
            "entity": self.entity,
            "claim_a": self.claim_a,
            "source_a": self.source_a,
            "claim_b": self.claim_b,
            "source_b": self.source_b,
            "resolved_value": self.resolved_value,
            "resolution": self.resolution,
            "policy_applied": self.policy_applied,
        }


@dataclass
class ContradictionResult:
    """The outcome of contradiction resolution for one entity."""
    contradiction: Contradiction
    is_unresolvable: bool
    audit_record: dict = field(default_factory=dict)


def resolve_contradiction(
    entity: str,
    claims: dict[str, Any],      # step_id -> claimed value
    policy: PrecedencePolicy = PrecedencePolicy.REPORT_BOTH,
    source_metadata: Optional[dict[str, dict]] = None,  # step_id -> metadata
) -> ContradictionResult:
    """
    Detect and resolve a contradiction between exactly two claims.

    When policy cannot resolve it, the contradiction is reported to the user
    (resolution="unresolvable"). Contradictions are never silently averaged away.
    """
    step_ids = list(claims.keys())
    if len(step_ids) < 2:
        raise ValueError("resolve_contradiction requires at least two claims")

    sid_a, sid_b = step_ids[0], step_ids[1]
    claim_a, claim_b = claims[sid_a], claims[sid_b]

    resolved_value: Optional[Any] = None
    resolution = "unresolvable"
    is_unresolvable = True

    if policy == PrecedencePolicy.REPORT_BOTH:
        resolution = "unresolvable: both values reported"
        is_unresolvable = True

    elif policy == PrecedencePolicy.DB_BEATS_EMAIL:
        meta = source_metadata or {}
        a_type = meta.get(sid_a, {}).get("source_type", "unknown")
        b_type = meta.get(sid_b, {}).get("source_type", "unknown")
        if a_type == "database":
            resolved_value = claim_a
            resolution = f"db_beats_email: {sid_a} (database) wins over {sid_b}"
            is_unresolvable = False
        elif b_type == "database":
            resolved_value = claim_b
            resolution = f"db_beats_email: {sid_b} (database) wins over {sid_a}"
            is_unresolvable = False
        else:
            resolution = "unresolvable: neither claim is a database record"
            is_unresolvable = True

    elif policy == PrecedencePolicy.USER_CONFIRMED_BEATS_INFERRED:
        meta = source_metadata or {}
        a_confirmed = meta.get(sid_a, {}).get("user_confirmed", False)
        b_confirmed = meta.get(sid_b, {}).get("user_confirmed", False)
        if a_confirmed and not b_confirmed:
            resolved_value = claim_a
            resolution = f"user_confirmed: {sid_a} wins"
            is_unresolvable = False
        elif b_confirmed and not a_confirmed:
            resolved_value = claim_b
            resolution = f"user_confirmed: {sid_b} wins"
            is_unresolvable = False
        else:
            resolution = "unresolvable: both or neither user-confirmed"
            is_unresolvable = True

    elif policy == PrecedencePolicy.MOST_RECENT:
        meta = source_metadata or {}
        ts_a = meta.get(sid_a, {}).get("timestamp", 0)
        ts_b = meta.get(sid_b, {}).get("timestamp", 0)
        if ts_a > ts_b:
            resolved_value = claim_a
            resolution = f"most_recent: {sid_a} (ts={ts_a}) wins"
            is_unresolvable = False
        elif ts_b > ts_a:
            resolved_value = claim_b
            resolution = f"most_recent: {sid_b} (ts={ts_b}) wins"
            is_unresolvable = False
        else:
            resolution = "unresolvable: identical timestamps"
            is_unresolvable = True

    contradiction = Contradiction(
        entity=entity,
        claim_a=claim_a,
        source_a=sid_a,
        claim_b=claim_b,
        source_b=sid_b,
        resolved_value=resolved_value,
        resolution=resolution,
        policy_applied=policy.value,
    )
    audit = {
        "entity": entity,
        "policy": policy.value,
        "is_unresolvable": is_unresolvable,
        "resolution": resolution,
    }
    logger.info("[Coordination] Contradiction: %s", audit)

    return ContradictionResult(
        contradiction=contradiction,
        is_unresolvable=is_unresolvable,
        audit_record=audit,
    )


# ---------------------------------------------------------------------------
# Bounded refinement
# ---------------------------------------------------------------------------

# Hard caps: at most one round per edge, at most this many total per run
_REFINEMENT_CAP_PER_EDGE = 1
_REFINEMENT_CAP_PER_RUN = 3


@dataclass
class RefinementState:
    """
    Tracks refinement requests within a single run to enforce caps.
    Instantiated once per supervisor run and threaded through coordination calls.
    """
    per_edge: dict[tuple[str, str], int] = field(default_factory=dict)  # (consumer, producer) -> count
    total: int = 0
    cap_per_edge: int = _REFINEMENT_CAP_PER_EDGE
    cap_per_run: int = _REFINEMENT_CAP_PER_RUN


def request_refinement(
    state: RefinementState,
    consumer_step_id: str,
    producer_step_id: str,
    narrowing_request: dict,
) -> tuple[bool, Optional[dict]]:
    """
    Request one narrowing round from an upstream agent.

    Returns (allowed, request_payload) where request_payload is None when
    the cap is reached or a cycle would be introduced.

    A refinement is a bounded re-invocation of an existing node, NOT a new
    edge. validate_dag_plan continues to reject cycles.
    """
    edge = (consumer_step_id, producer_step_id)
    edge_count = state.per_edge.get(edge, 0)

    if state.total >= state.cap_per_run:
        logger.warning(
            "[Coordination] Refinement cap per_run=%d reached. consumer=%s producer=%s",
            state.cap_per_run, consumer_step_id, producer_step_id,
        )
        return False, None

    if edge_count >= state.cap_per_edge:
        logger.warning(
            "[Coordination] Refinement cap per_edge=%d reached for edge (%s->%s).",
            state.cap_per_edge, consumer_step_id, producer_step_id,
        )
        return False, None

    # Check would-be cycle: a consumer cannot request refinement from a step
    # it also produces output for (the DAG validator handles true graph cycles;
    # this catches self-loops through refinement)
    if consumer_step_id == producer_step_id:
        logger.warning("[Coordination] Refinement cycle attempt: %s -> %s rejected.", consumer_step_id, producer_step_id)
        return False, None

    state.per_edge[edge] = edge_count + 1
    state.total += 1

    payload = {
        "refinement_request": True,
        "consumer_step_id": consumer_step_id,
        "producer_step_id": producer_step_id,
        "narrowing": narrowing_request,
        "round": edge_count + 1,
    }
    logger.info(
        "[Coordination] Refinement approved: %s -> %s round=%d",
        consumer_step_id, producer_step_id, edge_count + 1,
    )
    return True, payload
