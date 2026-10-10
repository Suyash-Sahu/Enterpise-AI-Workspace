"""
Phase 24: RunBlackboard owner/run isolation tests.

Same shape as tests/security/test_owner_isolation.py: real DB rows, no
mocks, proving that a second owner (or a second run) cannot read state
through any of RunBlackboard's public methods -- not "the code looks like it
scopes correctly," an actual attempted cross-owner/cross-run read that must
come back empty.
"""
import uuid

import pytest
from pydantic import BaseModel

from app.db.database import Base, SessionLocal, engine
from app.supervisor.blackboard import RunBlackboard

OWNER_A = "1"
OWNER_B = "2"


class _Secret(BaseModel):
    value: str


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_owner_b_cannot_read_owner_a_state_in_same_run():
    """
    Two owners sharing the same run_id (the pathological case -- a run_id
    collision or a deliberately shared value) must not see each other's
    entries. Every RunBlackboard read filters on (run_id, owner_id) together,
    never run_id alone.
    """
    db = SessionLocal()
    try:
        run_id = f"run_{uuid.uuid4().hex[:10]}"
        bb_a = RunBlackboard(db=db, run_id=run_id, owner_id=OWNER_A)
        bb_b = RunBlackboard(db=db, run_id=run_id, owner_id=OWNER_B)

        bb_a.put("secret", _Secret(value="owner-a-private-data"), written_by="step_1")

        assert bb_b.get("secret") is None
        assert bb_b.keys() == []
        assert bb_b.history("secret") == []

        # Owner A's own read is unaffected.
        assert bb_a.get("secret") == {"value": "owner-a-private-data"}
    finally:
        db.close()


def test_owner_b_cannot_read_owner_a_state_across_different_runs():
    """The ordinary case: different owners, different runs -- still isolated."""
    db = SessionLocal()
    try:
        bb_a = RunBlackboard(db=db, run_id=f"run_{uuid.uuid4().hex[:10]}", owner_id=OWNER_A)
        bb_b = RunBlackboard(db=db, run_id=f"run_{uuid.uuid4().hex[:10]}", owner_id=OWNER_B)

        bb_a.put("finding", _Secret(value="owner-a-run-1-finding"), written_by="step_1")

        assert bb_b.get("finding") is None
        assert bb_b.keys() == []
    finally:
        db.close()


def test_same_owner_cannot_read_across_different_runs():
    """
    Isolation is per-(run_id, owner_id), not per-owner alone -- one owner's
    two different runs must not bleed into each other either, since a
    replan/new run for the same user should not silently inherit a prior
    run's working memory.
    """
    db = SessionLocal()
    try:
        bb_run1 = RunBlackboard(db=db, run_id=f"run_{uuid.uuid4().hex[:10]}", owner_id=OWNER_A)
        bb_run2 = RunBlackboard(db=db, run_id=f"run_{uuid.uuid4().hex[:10]}", owner_id=OWNER_A)

        bb_run1.put("k", _Secret(value="run-1-value"), written_by="step_1")

        assert bb_run2.get("k") is None
    finally:
        db.close()
