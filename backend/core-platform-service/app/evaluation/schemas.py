from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class DatasetItemSchema(BaseModel):
    task_id: str
    task: str
    category: str
    complexity: str
    privacy_level: str
    expected_capability: str
    expected_execution_mode: str
    expected_approval_requirement: bool = False
    expected_answer: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class DatasetMetadataSchema(BaseModel):
    dataset_version: str
    dataset_hash: str
    file_path: str
    task_count: int
    categories: List[str]


class EvaluationConfigSchema(BaseModel):
    dataset_version: str = "amof_eval_v1"
    local_model: str = "ollama/qwen2.5-coder"
    cloud_model: str = "openrouter/anthropic/claude-3.5-sonnet"
    embedding_model: str = "nomic-embed-text"
    temperature: float = 0.0
    max_tokens: int = 2048
    cache_enabled: bool = True
    semantic_cache_enabled: bool = True
    verification_enabled: bool = True
    hitl_enabled: bool = True
    routing_configuration: str = "adaptive_amof_p7"
    seed: Optional[int] = 42
    execution_mode: str = "auto"  # auto, always_local, always_cloud, static_rule


class EvaluationResultItemSchema(BaseModel):
    task_id: str
    task_text: str
    category: str
    complexity: str
    privacy_level: str
    expected_capability: str
    expected_execution_mode: str
    actual_capability: Optional[str] = None
    actual_execution_mode: Optional[str] = None
    actual_model: Optional[str] = None
    routing_correct: Optional[bool] = None
    # Whether actual_capability matched expected_capability -- independent of
    # routing_correct, which only ever compares local/cloud placement. See
    # app/models/evaluation.py::EvaluationResult.capability_correct.
    capability_correct: Optional[bool] = None
    approval_required: Optional[bool] = None
    approval_status: Optional[str] = None
    execution_blocked: Optional[bool] = None
    approval_guard_triggered: Optional[bool] = None
    cache_hit: Optional[bool] = None
    verification_status: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    latency_ms: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None
    estimated_cost: Optional[float] = None
    # Predicted by the classifier at run time. Compared against the dataset's
    # `privacy_level` (ground truth) to produce precision/recall. These two
    # must never be assigned from the same source.
    privacy_classification: Optional[str] = None
    privacy_confidence: Optional[float] = None
    cloud_execution: Optional[bool] = None
    completion_success: Optional[bool] = None
    output_quality_score: Optional[float] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    trace_json: Optional[Dict[str, Any]] = None


class MetricSummarySchema(BaseModel):
    metric_name: str
    metric_value: Optional[float] = None
    denominator: Optional[float] = None
    numerator: Optional[float] = None
    metric_status: str = "AVAILABLE"  # AVAILABLE, METRIC_UNAVAILABLE, INSUFFICIENT_DATA
    metric_metadata: Optional[Dict[str, Any]] = None


class BaselineMetricsSchema(BaseModel):
    baseline_name: str  # ALWAYS_LOCAL, ALWAYS_CLOUD, STATIC_RULE, AMOF
    routing_accuracy: float
    completion_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_cost: float
    total_tokens: int
    privacy_leak_rate: float


class AblationConfigMetricsSchema(BaseModel):
    configuration_name: str  # BASELINE, + ROUTING, + VERIFICATION, + HITL, FULL AMOF, CACHE_OFF, CACHE_ON
    enabled_components: List[str]
    disabled_components: List[str]
    routing_accuracy: float
    completion_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_cost: float
    total_tokens: int
    cache_hit_rate: float
    # Added Phase 14: without these, the frontend's ablation_study dashboard
    # section (which shows completion/cost/privacy/verification per config)
    # had no honest source for its "privacy" and "verification" columns and
    # stayed permanently illustrative even when real ablation data existed.
    privacy_leak_rate: float
    # Fraction of items where verification ran (verification_status not
    # UNVERIFIED) that actually passed. 0.0, not fabricated, when
    # verification never ran for this config (e.g. the BASELINE arm).
    verification_pass_rate: float


class ParameterSweepMetricsSchema(BaseModel):
    """
    One point in the Phase 13 one-at-a-time router parameter sensitivity
    sweep (app/evaluation/ablation.py::AblationRunner.run_parameter_sweep).
    Distinct from AblationConfigMetricsSchema, which toggles whole
    components on/off -- this varies one numeric soft-constraint parameter
    at a time while holding the others at their config.py default.
    """

    configuration_name: str
    parameter: str  # ROUTER_LATENCY_BUDGET_MS | ROUTER_QUALITY_FLOOR | PRIVACY_CLOUD_CONFIDENCE
    value: float
    routing_accuracy: float
    completion_rate: float
    avg_latency_ms: float
    p95_latency_ms: float
    total_cost: float
    total_tokens: int
    # Count of RESTRICTED-labeled tasks in the sweep whose actual placement
    # was cloud. Phase 13's Definition of Done requires this to be 0 at
    # every swept value -- the hard-constraint regression check, not a
    # descriptive metric.
    privacy_hard_constraint_violations: int


class EvaluationRunCreateSchema(BaseModel):
    dataset_version: str = "amof_eval_v1"
    config: Optional[EvaluationConfigSchema] = None
    run_baselines: bool = True
    run_ablations: bool = True


class EvaluationRunResponseSchema(BaseModel):
    run_id: str
    status: str
    dataset_version: str
    dataset_hash: str
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    task_count: int
    completed_count: int
    failed_count: int
    configuration_json: Optional[Dict[str, Any]] = None
    git_commit: Optional[str] = None
    created_at: datetime
    metrics: List[MetricSummarySchema] = []
    baselines: List[BaselineMetricsSchema] = []
    ablations: List[AblationConfigMetricsSchema] = []
    # Non-None means save_artifacts() (JSON/CSV export) failed even though the
    # run itself completed -- surfaced here so a caller (API response, script)
    # sees it directly instead of only in a server log line. See
    # app/models/evaluation.py::EvaluationRun.artifact_error.
    artifact_error: Optional[str] = None
