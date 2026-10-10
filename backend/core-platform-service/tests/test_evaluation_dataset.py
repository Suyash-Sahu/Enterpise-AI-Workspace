import pytest
from app.evaluation.dataset_validator import DatasetValidator
from app.evaluation.dataset_loader import DatasetLoader


def test_dataset_validator_valid_item():
    valid_raw = {
        "task_id": "test_001",
        "task": "Summarize the latest report.",
        "category": "document_summary",
        "complexity": "simple",
        "privacy_level": "internal",
        "expected_capability": "document_summary",
        "expected_execution_mode": "local",
        "expected_approval_requirement": False,
    }
    item = DatasetValidator.validate_item(valid_raw)
    assert item.task_id == "test_001"
    assert item.expected_execution_mode == "local"


def test_dataset_validator_invalid_category():
    invalid_raw = {
        "task_id": "test_002",
        "task": "Do invalid thing",
        "category": "unsupported_cat",
        "complexity": "simple",
        "privacy_level": "internal",
        "expected_capability": "document_summary",
        "expected_execution_mode": "local",
    }
    with pytest.raises(ValueError) as exc:
        DatasetValidator.validate_item(invalid_raw)
    assert "Invalid category" in str(exc.value)


def test_dataset_loader_load():
    metadata, items = DatasetLoader.load_dataset("amof_eval_v1")
    assert metadata.dataset_version == "amof_eval_v1"
    assert len(metadata.dataset_hash) == 64
    assert len(items) > 0
    assert items[0].task_id == "task_001"


def test_calendar_action_rejected_no_handler_registered():
    """
    Regression (Phase 10 token audit, 2026-09-20): calendar_action's
    expected_capability "calendar.create" has no registered ExecutionHandler
    in execution/registry.py, so every such task was guaranteed to fail
    regardless of routing/tokens. Removed from ALLOWED_CATEGORIES until a
    real handler exists -- re-adding a calendar_action line must fail loudly
    at validation, not load a task that can never succeed.
    """
    raw = {
        "task_id": "test_calendar",
        "task": "Create a calendar event.",
        "category": "calendar_action",
        "complexity": "simple",
        "privacy_level": "internal",
        "expected_capability": "calendar.create",
        "expected_execution_mode": "cloud",
    }
    with pytest.raises(ValueError) as exc:
        DatasetValidator.validate_item(raw)
    assert "Invalid category" in str(exc.value)


def test_benchmark_dataset_has_no_calendar_action_tasks():
    """
    The live amof_eval_v1 dataset must not contain calendar_action tasks
    (removed 2026-09-20 -- see test above) until calendar.create has a real
    handler registered.
    """
    _, items = DatasetLoader.load_dataset("amof_eval_v1")
    categories = {item.category for item in items}
    assert "calendar_action" not in categories
    assert not any(item.expected_capability == "calendar.create" for item in items)


# --- Phase 12: expanded benchmark (amof_eval_v2) --------------------------


def test_dataset_validator_accepts_restricted_privacy_level():
    """
    Regression: SensitivityLabel.RESTRICTED (app/privacy/contracts.py) is a
    real, fourth privacy tier, but the validator only ever allowed three
    ("public", "internal", "confidential"). No benchmark task could exercise
    the router's absolute privacy floor until this was fixed (Phase 12,
    2026-09-20).
    """
    raw = {
        "task_id": "test_restricted",
        "task": "Run a query, noting this credential: AKIAABCDEFGHIJKLMNOP.",
        "category": "database_query",
        "complexity": "medium",
        "privacy_level": "restricted",
        "expected_capability": "database_query",
        "expected_execution_mode": "local",
    }
    item = DatasetValidator.validate_item(raw)
    assert item.privacy_level == "restricted"


def test_dataset_loader_load_v2():
    metadata, items = DatasetLoader.load_dataset("amof_eval_v2")
    assert metadata.dataset_version == "amof_eval_v2"
    assert len(metadata.dataset_hash) == 64
    # 9 tasks carried over from v1 + 11 new (Phase 12 expansion).
    assert len(items) == 20
    task_ids = [item.task_id for item in items]
    assert len(task_ids) == len(set(task_ids)), "duplicate task_id in amof_eval_v2"


def test_amof_eval_v2_has_no_calendar_action_tasks():
    """Same invariant as v1 -- expansion must not resurrect the removed category."""
    _, items = DatasetLoader.load_dataset("amof_eval_v2")
    categories = {item.category for item in items}
    assert "calendar_action" not in categories


def test_amof_eval_v2_coverage_all_four_privacy_tiers_present():
    """
    Phase 12 Definition of Done requires PUBLIC/INTERNAL/CONFIDENTIAL/
    RESTRICTED coverage in the expanded benchmark, not just schema support
    for the value.
    """
    _, items = DatasetLoader.load_dataset("amof_eval_v2")
    report = DatasetValidator.coverage_report(items)
    assert report["tiers_present"] == ["confidential", "internal", "public", "restricted"]


def test_amof_eval_v2_coverage_no_thin_categories():
    """
    Every task category should be exercised across at least 2 privacy tiers,
    so the benchmark can actually show tier-dependent routing behavior within
    each category, not just across categories.
    """
    _, items = DatasetLoader.load_dataset("amof_eval_v2")
    report = DatasetValidator.coverage_report(items)
    assert report["thin_categories"] == {}


def test_amof_eval_v2_restricted_tasks_always_expect_local():
    """
    RESTRICTED is the router's non-relaxable hard floor (see
    docs/research/methodology.md); every RESTRICTED task in the benchmark
    must expect local execution, including in categories (text_generation,
    communication_action) whose other tasks expect cloud.
    """
    _, items = DatasetLoader.load_dataset("amof_eval_v2")
    restricted = [item for item in items if item.privacy_level == "restricted"]
    assert len(restricted) >= 3
    assert all(item.expected_execution_mode == "local" for item in restricted)


def test_amof_eval_v2_no_fabricated_capability():
    """
    Every expected_capability must correspond to a real registered handler --
    a task whose capability can never succeed is fabricated ground truth, the
    exact defect that got calendar_action removed from v1.
    """
    from app.execution.registry import task_registry

    _, items = DatasetLoader.load_dataset("amof_eval_v2")
    for item in items:
        task_registry.get_handler(item.expected_capability)  # raises if unregistered
