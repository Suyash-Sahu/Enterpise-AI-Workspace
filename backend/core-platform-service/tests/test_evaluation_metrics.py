import pytest
from app.evaluation.schemas import EvaluationResultItemSchema
from app.evaluation.metrics import MetricsEngine


def test_metrics_calculation_fixtures():
    # 2 tasks: 1 correct routing, 1 incorrect routing
    res1 = EvaluationResultItemSchema(
        task_id="t1",
        task_text="Task 1",
        category="document_summary",
        complexity="simple",
        privacy_level="internal",
        expected_capability="document_summary",
        expected_execution_mode="local",
        actual_capability="document_summary",
        actual_execution_mode="local",
        routing_correct=True,
        capability_correct=True,
        completion_success=True,
        latency_ms=100.0,
        input_tokens=100,
        output_tokens=50,
        total_tokens=150,
        estimated_cost=0.0,
        cloud_execution=False,
    )
    res2 = EvaluationResultItemSchema(
        task_id="t2",
        task_text="Task 2",
        category="text_generation",
        complexity="complex",
        privacy_level="confidential",
        expected_capability="text_generation",
        expected_execution_mode="local",
        actual_capability="text_generation",
        actual_execution_mode="cloud",
        routing_correct=False,
        capability_correct=True,
        completion_success=True,
        latency_ms=300.0,
        input_tokens=200,
        output_tokens=100,
        total_tokens=300,
        estimated_cost=0.0009,
        cloud_execution=True,
    )

    metrics = MetricsEngine.calculate_metrics([res1, res2])
    m_dict = {m.metric_name: m.metric_value for m in metrics}

    assert m_dict["routing_accuracy"] == 0.5
    # Independent from routing_accuracy: both tasks have the right
    # capability (one via a wrong placement, one via a right one), so
    # capability_accuracy is 1.0 even though routing_accuracy is 0.5 --
    # proves the two are not coupled (smoke evaluation, 2026-09-20).
    assert m_dict["capability_accuracy"] == 1.0
    assert m_dict["completion_rate"] == 1.0
    assert m_dict["avg_latency_ms"] == 200.0
    assert m_dict["total_tokens"] == 450.0
    assert m_dict["privacy_leak_rate"] == 0.5
