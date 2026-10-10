import copy
import logging
from typing import List
from sqlalchemy.orm import Session

from app.core.config import settings
from app.evaluation.schemas import (
    DatasetItemSchema,
    EvaluationConfigSchema,
    AblationConfigMetricsSchema,
    ParameterSweepMetricsSchema,
)
from app.evaluation.executor import TaskExecutor
from app.evaluation.metrics import MetricsEngine

logger = logging.getLogger(__name__)


class AblationRunner:
    """
    Executes component ablation studies on the evaluation dataset by toggling routing, verification, HITL, and caching.
    """

    ABLATION_STUDIES = [
        {
            "name": "BASELINE",
            "enabled": ["local_execution"],
            "disabled": ["adaptive_routing", "verification", "hitl", "cache"],
            "override_mode": "always_local",
            "cache_enabled": False,
            "hitl_enabled": False,
            "verification_enabled": False,
        },
        {
            "name": "+ ROUTING",
            "enabled": ["local_execution", "adaptive_routing"],
            "disabled": ["verification", "hitl", "cache"],
            "override_mode": None,
            "cache_enabled": False,
            "hitl_enabled": False,
            "verification_enabled": False,
        },
        {
            "name": "+ ROUTING + VERIFICATION",
            "enabled": ["local_execution", "adaptive_routing", "verification"],
            "disabled": ["hitl", "cache"],
            "override_mode": None,
            "cache_enabled": False,
            "hitl_enabled": False,
            "verification_enabled": True,
        },
        {
            "name": "+ ROUTING + VERIFICATION + HITL",
            "enabled": ["local_execution", "adaptive_routing", "verification", "hitl"],
            "disabled": ["cache"],
            "override_mode": None,
            "cache_enabled": False,
            "hitl_enabled": True,
            "verification_enabled": True,
        },
        {
            "name": "+ ROUTING + ATGO (DAG)",
            "enabled": ["local_execution", "adaptive_routing", "atgo_dag"],
            "disabled": ["cdrp", "verification", "hitl", "cache"],
            "override_mode": None,
            "cache_enabled": False,
            "hitl_enabled": False,
            "verification_enabled": False,
        },
        {
            "name": "+ ROUTING + ATGO + CDRP",
            "enabled": ["local_execution", "adaptive_routing", "atgo_dag", "cdrp"],
            "disabled": ["verification", "hitl", "cache"],
            "override_mode": None,
            "cache_enabled": False,
            "hitl_enabled": False,
            "verification_enabled": False,
        },
        {
            "name": "FULL AMOF",
            "enabled": ["local_execution", "adaptive_routing", "atgo_dag", "cdrp", "verification", "hitl", "cache"],
            "disabled": [],
            "override_mode": None,
            "cache_enabled": True,
            "hitl_enabled": True,
            "verification_enabled": True,
        },
        {
            "name": "CACHE_OFF",
            "enabled": ["local_execution", "adaptive_routing", "verification", "hitl"],
            "disabled": ["cache"],
            "override_mode": None,
            "cache_enabled": False,
            "hitl_enabled": True,
            "verification_enabled": True,
        },
        {
            "name": "CACHE_ON",
            "enabled": ["local_execution", "adaptive_routing", "verification", "hitl", "cache"],
            "disabled": [],
            "override_mode": None,
            "cache_enabled": True,
            "hitl_enabled": True,
            "verification_enabled": True,
        },
    ]

    # Phase 13: one-at-a-time sensitivity sweep over the router's actual
    # numeric soft-constraint parameters (see docs/research/methodology.md).
    # Deliberately one-at-a-time, not a full 3-factor factorial -- per
    # PHASE_13.md's own risk note, a joint sweep combinatorially explodes and
    # this design already answers RQ4 (per-parameter sensitivity) without it.
    # Values bracket each parameter's config.py default on both sides, chosen
    # against the real RUNTIME_MODEL_PROFILES_LOCAL/_CLOUD numbers so the low
    # end actually excludes at least one real candidate rather than being a
    # no-op: 1500ms is below every local model's est_latency_ms (2100/4200)
    # and below the free cloud model's (1900), so it forces a real winner
    # change for cloud-eligible content (see the sweep test).
    # No complexity parameter: Phase 11 formally scoped complexity out of the
    # routing methodology, so there is nothing to sweep for it.
    PARAMETER_SWEEP_STUDIES = [
        {"name": "latency_budget_ms=1500", "parameter": "ROUTER_LATENCY_BUDGET_MS", "value": 1500.0},
        {"name": "latency_budget_ms=8000_default", "parameter": "ROUTER_LATENCY_BUDGET_MS", "value": 8000.0},
        {"name": "latency_budget_ms=16000", "parameter": "ROUTER_LATENCY_BUDGET_MS", "value": 16000.0},
        {"name": "quality_floor=0.30", "parameter": "ROUTER_QUALITY_FLOOR", "value": 0.30},
        {"name": "quality_floor=0.55_default", "parameter": "ROUTER_QUALITY_FLOOR", "value": 0.55},
        {"name": "quality_floor=0.80", "parameter": "ROUTER_QUALITY_FLOOR", "value": 0.80},
        {"name": "cloud_confidence=0.50", "parameter": "PRIVACY_CLOUD_CONFIDENCE", "value": 0.50},
        {"name": "cloud_confidence=0.75_default", "parameter": "PRIVACY_CLOUD_CONFIDENCE", "value": 0.75},
        {"name": "cloud_confidence=0.90", "parameter": "PRIVACY_CLOUD_CONFIDENCE", "value": 0.90},
    ]

    @classmethod
    def run_parameter_sweep(
        cls,
        db: Session,
        tasks: List[DatasetItemSchema],
        base_config: EvaluationConfigSchema,
    ) -> List[ParameterSweepMetricsSchema]:
        """
        Runs `tasks` once per PARAMETER_SWEEP_STUDIES entry, each time
        overriding exactly one of settings.{ROUTER_LATENCY_BUDGET_MS,
        ROUTER_QUALITY_FLOOR, PRIVACY_CLOUD_CONFIDENCE} -- the same settings
        attributes app/privacy/router.py reads as its defaults, so this needs
        no new plumbing through the router/policy layer. Always restores the
        original value afterwards, even on failure, so one bad run can't
        leak an overridden threshold into whatever runs next in the process.

        Execution mode is left as `base_config.execution_mode` (normally
        "auto"), never overridden here -- unlike run_ablations' BASELINE arm,
        this sweep is specifically about how the adaptive router responds to
        each parameter, so pinning local/cloud would defeat the point.
        """
        results: List[ParameterSweepMetricsSchema] = []

        for study in cls.PARAMETER_SWEEP_STUDIES:
            attr = study["parameter"]
            original = getattr(settings, attr)
            setattr(settings, attr, study["value"])
            try:
                item_results = [
                    TaskExecutor.execute_task(db=db, task=task, config=base_config)
                    for task in tasks
                ]
            finally:
                setattr(settings, attr, original)

            # Hard-constraint regression check (Phase 13 Security
            # Considerations): no swept value may ever place RESTRICTED
            # content in the cloud. Checked against what actually happened
            # in this run, not a separate simulation, so it can't drift from
            # the real result.
            violations = sum(
                1
                for task, res in zip(tasks, item_results)
                if task.privacy_level == "restricted" and res.actual_execution_mode == "cloud"
            )
            if violations:
                logger.error(
                    "[AblationRunner] PRIVACY HARD-CONSTRAINT VIOLATION: %d RESTRICTED "
                    "task(s) routed to cloud under %s=%s",
                    violations,
                    attr,
                    study["value"],
                )

            metrics_list = MetricsEngine.calculate_metrics(item_results)
            m_map = {m.metric_name: m.metric_value for m in metrics_list}

            def _num(key: str, default: float = 0.0) -> float:
                val = m_map.get(key)
                return default if val is None else val

            results.append(
                ParameterSweepMetricsSchema(
                    configuration_name=study["name"],
                    parameter=attr,
                    value=study["value"],
                    routing_accuracy=_num("routing_accuracy"),
                    completion_rate=_num("completion_rate"),
                    avg_latency_ms=_num("avg_latency_ms"),
                    p95_latency_ms=_num("p95_latency_ms"),
                    total_cost=_num("total_cost_usd"),
                    total_tokens=int(_num("total_tokens")),
                    privacy_hard_constraint_violations=violations,
                )
            )

        return results

    @classmethod
    def run_ablations(
        cls,
        db: Session,
        tasks: List[DatasetItemSchema],
        base_config: EvaluationConfigSchema,
    ) -> List[AblationConfigMetricsSchema]:
        ablation_metrics_list: List[AblationConfigMetricsSchema] = []

        for study in cls.ABLATION_STUDIES:
            cfg = copy.deepcopy(base_config)
            cfg.cache_enabled = study["cache_enabled"]
            cfg.hitl_enabled = study["hitl_enabled"]
            cfg.verification_enabled = study["verification_enabled"]

            items_results = []
            for task in tasks:
                res = TaskExecutor.execute_task(
                    db=db,
                    task=task,
                    config=cfg,
                    override_mode=study["override_mode"],
                )
                items_results.append(res)

            metrics_list = MetricsEngine.calculate_metrics(items_results)
            m_map = {m.metric_name: m.metric_value for m in metrics_list}

            # See the identical helper in baselines.py: .get(key, default)
            # only falls back when the key is absent, not when its value is
            # the honest None that an unmeasurable metric now reports.
            def _num(key: str, default: float = 0.0) -> float:
                val = m_map.get(key)
                return default if val is None else val

            # Computed directly from item results, not MetricsEngine: there
            # is no run-level "verification pass rate" metric today (only
            # per-item verification_status), and adding one to MetricsEngine
            # for a single caller would be scope beyond what this phase asks
            # for. 0.0 when verification never ran for this config (e.g. the
            # BASELINE arm), not None/omitted -- the frontend field is a
            # required float, and "never ran" is a real, honest answer.
            verified = [r for r in items_results if r.verification_status and r.verification_status != "UNVERIFIED"]
            verification_pass_rate = (
                sum(1 for r in verified if r.verification_status == "PASSED") / len(verified)
                if verified
                else 0.0
            )

            a_schema = AblationConfigMetricsSchema(
                configuration_name=study["name"],
                enabled_components=study["enabled"],
                disabled_components=study["disabled"],
                routing_accuracy=_num("routing_accuracy"),
                completion_rate=_num("completion_rate"),
                avg_latency_ms=_num("avg_latency_ms"),
                p95_latency_ms=_num("p95_latency_ms"),
                total_cost=_num("total_cost_usd"),
                total_tokens=int(_num("total_tokens")),
                cache_hit_rate=_num("cache_hit_rate"),
                privacy_leak_rate=_num("privacy_leak_rate"),
                verification_pass_rate=round(verification_pass_rate, 4),
            )
            ablation_metrics_list.append(a_schema)

        return ablation_metrics_list
