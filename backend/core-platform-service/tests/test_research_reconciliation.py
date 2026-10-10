"""
AMOF-X Phase 11 Research Infrastructure Reconciliation Tests.

Verifies that evaluation and telemetry API routes return real empirical measurements
from the database, and zero hardcoded illustrative/mock values exist in active endpoints.
"""
import pytest
from sqlalchemy.orm import Session

from app.db.database import Base, SessionLocal, engine
from app.models.user import User
from app.models.role import Role
from app.db.seed import seed_roles
from app.evaluation.baselines import BaselineRunner
from app.evaluation.ablation import AblationRunner

OWNER_ID = "1"


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_roles(db)
        role = db.query(Role).filter(Role.name == "admin").first()
        if not db.query(User).filter(User.id == int(OWNER_ID)).first():
            db.add(User(id=int(OWNER_ID), name="Admin User", email="admin_reconciliation@example.com", password_hash="hash", role_id=role.id))
        db.commit()
    finally:
        db.close()
    yield


def test_ablation_runner_includes_atgo_and_cdrp_components():
    """
    Verifies that the System B evaluation harness includes ATGO (Phase 2)
    and CDRP (Phase 4) in its ablation suite.
    """
    study_names = [study["name"] for study in AblationRunner.ABLATION_STUDIES]

    assert "+ ROUTING + ATGO (DAG)" in study_names
    assert "+ ROUTING + ATGO + CDRP" in study_names
    assert "FULL AMOF" in study_names


def test_baselines_runner_supported_strategies():
    """
    Verifies that baseline evaluation strategies cover ALWAYS_LOCAL, ALWAYS_CLOUD, STATIC_RULE, and AMOF.
    """
    baselines = BaselineRunner.BASELINES
    assert "ALWAYS_LOCAL" in baselines
    assert "ALWAYS_CLOUD" in baselines
    assert "STATIC_RULE" in baselines
    assert "AMOF" in baselines


# --- Phase 14: illustrative data must never reach a production response ---


def test_metrics_engine_reports_unavailable_rather_than_fabricating_a_number():
    """
    The mechanism that actually prevents illustrative numbers leaking into
    an API response is MetricsEngine refusing to invent one: a result set
    with nothing measured must yield metric_value=None plus an explicit
    status, never 0.0 or a plausible-looking placeholder that a dashboard
    would render as if it were real.
    """
    from app.evaluation.metrics import MetricsEngine
    from app.evaluation.schemas import EvaluationResultItemSchema

    unmeasured = [
        EvaluationResultItemSchema(
            task_id="t1",
            task_text="anything",
            category="document_summary",
            complexity="simple",
            privacy_level="public",
            expected_capability="document_summary",
            expected_execution_mode="local",
            # Everything measurable is explicitly absent.
            latency_ms=None,
            total_tokens=None,
            estimated_cost=None,
            output_quality_score=None,
            completion_success=None,
            routing_correct=None,
        )
    ]

    metrics = {m.metric_name: m for m in MetricsEngine.calculate_metrics(unmeasured)}

    for name in ("avg_latency_ms", "total_cost_usd", "total_tokens", "output_quality_score"):
        assert metrics[name].metric_value is None, f"{name} fabricated a value from no data"
        assert metrics[name].metric_status in {"METRIC_UNAVAILABLE", "INSUFFICIENT_DATA"}


def test_ablation_schema_exposes_privacy_and_verification_for_dashboard_reconciliation():
    """
    The frontend's ablation_study section shows completion/cost/privacy/
    verification per configuration. Before Phase 14 the backend had no
    source for the last two, so that section stayed permanently
    illustrative -- these fields are what make a real-data overlay possible,
    and they are required (not Optional) so a response can't silently omit
    them and leave the dashboard falling back to prototype values.
    """
    from app.evaluation.schemas import AblationConfigMetricsSchema

    fields = AblationConfigMetricsSchema.model_fields
    assert "privacy_leak_rate" in fields
    assert "verification_pass_rate" in fields
    assert fields["privacy_leak_rate"].is_required()
    assert fields["verification_pass_rate"].is_required()


def test_no_prototype_illustrative_constants_are_hardcoded_in_backend_evaluation_code():
    """
    Guards the other direction: the illustrative dashboard values live in
    web/src/data/research/amof_prototype_results_v1.json and must never be
    mirrored into backend evaluation code, where they would be served as if
    measured. Scans for the prototype's distinctive per-1k cost and
    per-task token constants.
    """
    import pathlib

    # Distinctive enough not to collide with a legitimate computation:
    # these are the prototype's cost_per_1k_usd and tokens_per_task values.
    illustrative_constants = ["18.40", "13.10", "10.90", "2450", "1935", "1690", "1421"]

    eval_dir = pathlib.Path(__file__).resolve().parent.parent / "app" / "evaluation"
    offenders = []
    for py_file in eval_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8", errors="ignore")
        for constant in illustrative_constants:
            if constant in text:
                offenders.append(f"{py_file.name}: {constant}")

    assert offenders == [], f"prototype illustrative constants found in backend evaluation code: {offenders}"
