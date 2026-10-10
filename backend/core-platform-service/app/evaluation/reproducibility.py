import hashlib
import json
import subprocess
from typing import Dict, Any, Optional


class ReproducibilityManager:
    """
    Handles hash calculation for datasets, configurations, and git commit retrieval to ensure reproducible evaluation runs.
    """

    @staticmethod
    def get_git_commit() -> Optional[str]:
        try:
            output = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            )
            return output.decode("utf-8").strip()
        except Exception:
            return "unknown-commit"

    @staticmethod
    def calculate_config_hash(config_dict: Dict[str, Any]) -> str:
        canonical_json = json.dumps(config_dict, sort_keys=True)
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    @classmethod
    def build_run_metadata(cls, dataset_hash: str, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "git_commit": cls.get_git_commit(),
            "dataset_hash": dataset_hash,
            "configuration_hash": cls.calculate_config_hash(config_dict),
            "reproducible": True,
        }
