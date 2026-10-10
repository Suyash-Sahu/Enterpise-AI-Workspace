import json
import logging
from collections import Counter
from typing import Dict, List, Tuple
from app.evaluation.schemas import DatasetItemSchema

logger = logging.getLogger(__name__)


class DatasetValidator:
    """
    Validates evaluation dataset JSONL structure and labels before evaluation runs.
    """

    ALLOWED_CATEGORIES = {
        "document_summary",
        "rag_search",
        "rag_answer",
        "database_query",
        "text_generation",
        "communication_action",
        # calendar_action removed (Phase 10 token audit, 2026-09-20): its
        # expected_capability "calendar.create" has no registered
        # ExecutionHandler in execution/registry.py, so every such task was
        # guaranteed to fail regardless of routing/tokens. Re-add only once
        # a real handler exists.
    }
    ALLOWED_COMPLEXITIES = {"simple", "medium", "complex"}
    # "restricted" added (Phase 12, 2026-09-20): the fourth SensitivityLabel
    # tier (app/privacy/contracts.py::SensitivityLabel.RESTRICTED) had no
    # corresponding dataset value, so no benchmark task could ever exercise
    # the router's absolute-floor privacy behavior.
    ALLOWED_PRIVACY_LEVELS = {"public", "internal", "confidential", "restricted"}
    ALLOWED_MODES = {"local", "cloud"}

    @classmethod
    def validate_item(cls, raw_item: dict) -> DatasetItemSchema:
        item = DatasetItemSchema(**raw_item)
        if item.category not in cls.ALLOWED_CATEGORIES:
            raise ValueError(f"Invalid category '{item.category}' in task {item.task_id}")
        if item.complexity not in cls.ALLOWED_COMPLEXITIES:
            raise ValueError(f"Invalid complexity '{item.complexity}' in task {item.task_id}")
        if item.privacy_level not in cls.ALLOWED_PRIVACY_LEVELS:
            raise ValueError(f"Invalid privacy_level '{item.privacy_level}' in task {item.task_id}")
        if item.expected_execution_mode not in cls.ALLOWED_MODES:
            raise ValueError(f"Invalid expected_execution_mode '{item.expected_execution_mode}' in task {item.task_id}")
        return item

    @classmethod
    def validate_file_content(cls, content: str) -> Tuple[bool, List[DatasetItemSchema], str]:
        items: List[DatasetItemSchema] = []
        lines = content.strip().splitlines()
        if not lines:
            return False, [], "Dataset file is empty"

        for idx, line in enumerate(lines, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                raw_item = json.loads(line)
                item = cls.validate_item(raw_item)
                items.append(item)
            except Exception as e:
                return False, [], f"Line {idx} validation error: {str(e)}"

        if not items:
            return False, [], "No valid evaluation tasks found in dataset"

        return True, items, "Dataset validation successful"

    @classmethod
    def coverage_matrix(cls, items: List[DatasetItemSchema]) -> Dict[Tuple[str, str], int]:
        """
        Counts tasks per (category, privacy_level) design cell.

        Phase 12's benchmark matrix is category x privacy tier; this is the
        one place that count is computed, so the coverage test and any future
        reporting stay in sync rather than each re-deriving it.
        """
        return dict(Counter((item.category, item.privacy_level) for item in items))

    @classmethod
    def coverage_report(cls, items: List[DatasetItemSchema]) -> Dict[str, object]:
        """
        Summarizes design-matrix balance: which privacy tiers appear at all,
        and which categories have fewer than 2 tiers represented (a category
        with only one tier can't show the router's tier-dependent behavior
        within that category).
        """
        matrix = cls.coverage_matrix(items)
        tiers_present = {tier for (_, tier) in matrix}
        tiers_by_category: Dict[str, set] = {}
        for category, tier in matrix:
            tiers_by_category.setdefault(category, set()).add(tier)
        thin_categories = {
            cat: sorted(tiers) for cat, tiers in tiers_by_category.items() if len(tiers) < 2
        }
        return {
            "matrix": matrix,
            "tiers_present": sorted(tiers_present),
            "categories_covered": sorted(tiers_by_category.keys()),
            "thin_categories": thin_categories,
        }
