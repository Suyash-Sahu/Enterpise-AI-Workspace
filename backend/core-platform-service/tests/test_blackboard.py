"""
Phase 24: RunBlackboard unit tests (put/get/history/append-only/validation/cap).
"""
import uuid

import pytest
from pydantic import BaseModel

from app.core.config import settings
from app.db.database import Base, SessionLocal, engine
from app.supervisor.blackboard import BlackboardCapacityExceeded, RunBlackboard


class _DummyOutput(BaseModel):
    value: str


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def _new_blackboard(db, owner_id: str = "1") -> RunBlackboard:
    return RunBlackboard(db=db, run_id=f"run_{uuid.uuid4().hex[:10]}", owner_id=owner_id)


def test_put_get_round_trip():
    db = SessionLocal()
    try:
        bb = _new_blackboard(db)
        bb.put("greeting", _DummyOutput(value="hello"), written_by="step_1")
        assert bb.get("greeting") == {"value": "hello"}
    finally:
        db.close()


def test_get_missing_key_returns_none():
    db = SessionLocal()
    try:
        bb = _new_blackboard(db)
        assert bb.get("never_written") is None
    finally:
        db.close()


def test_history_is_append_only_and_ordered():
    db = SessionLocal()
    try:
        bb = _new_blackboard(db)
        bb.put("k", _DummyOutput(value="first"), written_by="step_1")
        bb.put("k", _DummyOutput(value="second"), written_by="step_2")

        # get() returns the latest ...
        assert bb.get("k") == {"value": "second"}
        # ... but history() still has both, in write order -- the earlier
        # write is never destroyed.
        hist = bb.history("k")
        assert hist == [{"value": "first"}, {"value": "second"}]
    finally:
        db.close()


def test_keys_lists_every_distinct_key():
    db = SessionLocal()
    try:
        bb = _new_blackboard(db)
        bb.put("a", _DummyOutput(value="1"))
        bb.put("b", _DummyOutput(value="2"))
        bb.put("a", _DummyOutput(value="3"))
        assert bb.keys() == ["a", "b"]
    finally:
        db.close()


def test_unvalidated_write_is_rejected():
    db = SessionLocal()
    try:
        bb = _new_blackboard(db)
        with pytest.raises(ValueError):
            bb.put("bad", {"value": "raw dict, not a BaseModel"})
        # Confirm nothing was actually persisted for the rejected write.
        assert bb.get("bad") is None
    finally:
        db.close()


def test_entry_count_cap_is_enforced(monkeypatch):
    monkeypatch.setattr(settings, "BLACKBOARD_MAX_ENTRIES", 3)
    db = SessionLocal()
    try:
        bb = _new_blackboard(db)
        bb.put("k1", _DummyOutput(value="1"))
        bb.put("k2", _DummyOutput(value="2"))
        bb.put("k3", _DummyOutput(value="3"))
        with pytest.raises(BlackboardCapacityExceeded):
            bb.put("k4", _DummyOutput(value="4"))
        # The rejected write must not have been persisted -- the cap fails
        # loudly, it does not silently truncate.
        assert bb.get("k4") is None
        assert len(bb.keys()) == 3
    finally:
        db.close()


def test_byte_size_cap_is_enforced(monkeypatch):
    monkeypatch.setattr(settings, "BLACKBOARD_MAX_BYTES", 50)
    db = SessionLocal()
    try:
        bb = _new_blackboard(db)
        with pytest.raises(BlackboardCapacityExceeded):
            bb.put("big", _DummyOutput(value="x" * 200))
        assert bb.get("big") is None
    finally:
        db.close()
