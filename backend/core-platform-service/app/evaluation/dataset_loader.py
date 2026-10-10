import hashlib
import os
from typing import List, Tuple
from app.evaluation.schemas import DatasetItemSchema, DatasetMetadataSchema
from app.evaluation.dataset_validator import DatasetValidator


class DatasetLoader:
    """
    Loads versioned evaluation datasets from the datasets directory and calculates SHA-256 hashes.
    """

    BASE_DIR = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "evaluation",
        "datasets",
    )

    @classmethod
    def get_dataset_path(cls, version: str = "amof_eval_v1") -> str:
        filename = version if version.endswith(".jsonl") else f"{version}.jsonl"
        return os.path.join(cls.BASE_DIR, filename)

    @classmethod
    def calculate_hash(cls, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @classmethod
    def load_dataset(cls, version: str = "amof_eval_v1") -> Tuple[DatasetMetadataSchema, List[DatasetItemSchema]]:
        file_path = cls.get_dataset_path(version)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Evaluation dataset file not found at: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        is_valid, items, msg = DatasetValidator.validate_file_content(content)
        if not is_valid:
            raise ValueError(f"Dataset validation failed for '{version}': {msg}")

        file_hash = cls.calculate_hash(content)
        categories = sorted(list({item.category for item in items}))

        metadata = DatasetMetadataSchema(
            dataset_version=version,
            dataset_hash=file_hash,
            file_path=file_path,
            task_count=len(items),
            categories=categories,
        )

        return metadata, items
