import pytest
from app.evaluation.reproducibility import ReproducibilityManager


def test_reproducibility_config_hash():
    config1 = {"mode": "auto", "temp": 0.0, "seed": 42}
    config2 = {"seed": 42, "temp": 0.0, "mode": "auto"}
    config3 = {"mode": "auto", "temp": 0.5, "seed": 42}

    hash1 = ReproducibilityManager.calculate_config_hash(config1)
    hash2 = ReproducibilityManager.calculate_config_hash(config2)
    hash3 = ReproducibilityManager.calculate_config_hash(config3)

    # Order invariance in canonical JSON hash
    assert hash1 == hash2
    # Different config produces different hash
    assert hash1 != hash3


def test_reproducibility_git_commit():
    commit = ReproducibilityManager.get_git_commit()
    assert isinstance(commit, str)
    assert len(commit) > 0
