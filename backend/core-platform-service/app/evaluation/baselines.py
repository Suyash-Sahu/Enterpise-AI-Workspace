from typing import List
from sqlalchemy.orm import Session

from app.evaluation.schemas import (
    DatasetItemSchema,
    EvaluationConfigSchema,
    BaselineMetricsSchema,
)
from app.evaluation.executor import TaskExecutor
from app.evaluation.metrics import MetricsEngine


class BaselineRunner:
    """
    Executes controlled baseline strategies (ALWAYS_LOCAL, ALWAYS_CLOUD, STATIC_RULE, AMOF) on the evaluation dataset.
    """

    BASELINES = ["ALWAYS_LOCAL", "ALWAYS_CLOUD", "STATIC_RULE", "AMOF"]

    @classmethod
    def run_baselines(
        cls,
        db: Session,
        tasks: List[DatasetItemSchema],
        config: EvaluationConfigSchema,
    ) -> List[BaselineMetricsSchema]:
        baseline_results: List[BaselineMetricsSchema] = []

        for b_name in cls.BASELINES:
            mode_override = None
            if b_name == "ALWAYS_LOCAL":
                mode_override = "always_local"
            elif b_name == "ALWAYS_CLOUD":
                mode_override = "always_cloud"
            elif b_name == "STATIC_RULE":
                mode_override = "static_rule"
            elif b_name == "AMOF":
                mode_override = None

            items_results = []
            for task in tasks:
                res = TaskExecutor.execute_task(db=db, task=task, config=config, override_mode=mode_override)
                items_results.append(res)

            metrics_list = MetricsEngine.calculate_metrics(items_results)
            m_map = {m.metric_name: m.metric_value for m in metrics_list}

            # m_map.get(key, default) only falls back when the KEY is absent.
            # Since Week 1, a metric MetricsEngine can't compute (e.g. every
            # task in this baseline failed before reporting real tokens) has
            # the key present with value None -- the honest replacement for
            # the old fabricated-default behaviour. .get(key, default) still
            # returns that None, and int(None) below used to crash the first
            # time an all-failure baseline run (ALWAYS_LOCAL with Ollama
            # unreachable) actually happened.
            def _num(key: str, default: float = 0.0) -> float:
                val = m_map.get(key)
                return default if val is None else val

            b_schema = BaselineMetricsSchema(
                baseline_name=b_name,
                routing_accuracy=_num("routing_accuracy"),
                completion_rate=_num("completion_rate"),
                avg_latency_ms=_num("avg_latency_ms"),
                p95_latency_ms=_num("p95_latency_ms"),
                total_cost=_num("total_cost_usd"),
                total_tokens=int(_num("total_tokens")),
                privacy_leak_rate=_num("privacy_leak_rate"),
            )
            baseline_results.append(b_schema)

        return baseline_results
