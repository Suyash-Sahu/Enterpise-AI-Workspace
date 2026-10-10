"""
AMOF-X Phase 8: event publishing tests.

Redis is confirmed unreachable in this dev environment (the same
degraded-mode condition app/cache/ already documents and every other
Redis-touching code path this session hits), so a small in-process fake
Redis Stream stands in for `redis_client.get_raw_client()`. This is not a
mock of EventPublisher itself -- it exercises the real
EventPublisher.publish() -> XADD serialization and a real XRANGE read-back,
just against a fake transport instead of a live server, the same
"the real code runs, only the network boundary is faked" approach the
existing Google-connector tests already use for Gmail/Drive.
"""
import json
from unittest.mock import patch

from app.cache import client as cache_client_module
from app.events.publisher import STREAM_KEY, event_publisher
from app.events.schema import Event, EventType


class _FakeRedisStream:
    """Minimal XADD/XRANGE/GET/SET emulation -- just enough for these tests."""

    def __init__(self):
        self.entries: list[tuple[str, dict]] = []
        self._counter = 0
        self._kv: dict[str, str] = {}

    def xadd(self, key, fields):
        self._counter += 1
        entry_id = f"{self._counter}-0"
        self.entries.append((entry_id, dict(fields)))
        return entry_id

    def xrange(self, key, min="-", max="+", count=None):
        entries = self.entries
        if isinstance(min, str) and min.startswith("("):
            after = min[1:]
            entries = [e for e in entries if e[0] > after]
        if count:
            entries = entries[:count]
        return entries

    def get(self, key):
        return self._kv.get(key)

    def set(self, key, value):
        self._kv[key] = value
        return True


def test_publish_pushes_a_real_xadd_entry(monkeypatch):
    fake = _FakeRedisStream()
    monkeypatch.setattr(cache_client_module.redis_client, "get_raw_client", lambda: fake)

    event = Event(event_type=EventType.TASK_CREATED, owner_id="42", payload={"task_id": "task_1"})
    entry_id = event_publisher.publish(event)

    assert entry_id is not None
    assert len(fake.entries) == 1
    _, fields = fake.entries[0]
    assert fields["event_type"] == "task_created"
    assert fields["owner_id"] == "42"
    data = json.loads(fields["data"])
    assert data["payload"]["task_id"] == "task_1"


def test_publish_degrades_gracefully_when_redis_unreachable(monkeypatch):
    monkeypatch.setattr(cache_client_module.redis_client, "get_raw_client", lambda: None)

    result = event_publisher.publish(Event(event_type=EventType.TASK_CREATED, owner_id="42"))

    assert result is None  # no raise, no crash


def test_xrange_read_back_matches_what_was_published(monkeypatch):
    fake = _FakeRedisStream()
    monkeypatch.setattr(cache_client_module.redis_client, "get_raw_client", lambda: fake)

    event_publisher.publish(Event(event_type=EventType.APPROVAL_REQUESTED, owner_id="7", payload={"approval_id": 99}))
    event_publisher.publish(Event(event_type=EventType.APPROVAL_GRANTED, owner_id="7", payload={"approval_id": 99}))

    read_back = fake.xrange(STREAM_KEY, min="-", max="+")
    types = [fields["event_type"] for _id, fields in read_back]
    assert types == ["approval_requested", "approval_granted"]


def test_supervisor_run_publishes_agent_and_verification_events(monkeypatch):
    """
    A real amof_supervisor.run() call (LLM stubbed, same pattern as
    tests/test_routing_decision_persistence.py) must land real
    agent_started/agent_completed/verification_completed events on the
    stream -- read back via XRANGE, not just "publish didn't throw".
    """
    fake = _FakeRedisStream()
    monkeypatch.setattr(cache_client_module.redis_client, "get_raw_client", lambda: fake)

    from app.db.database import SessionLocal
    from app.schemas.runtime import RuntimeGenerateResponse
    from app.supervisor.context import SupervisorContext
    from app.supervisor.supervisor import amof_supervisor

    mock_resp = RuntimeGenerateResponse(
        completion="Q3 revenue grew steadily across all three regional offices this quarter.",
        provider="mock_provider",
        model="mock_model",
        runtime="local",
    )

    db = SessionLocal()
    try:
        context = SupervisorContext(
            owner_id="1",
            question="Write a brief status summary.",
            execution_mode="local",
            hitl_enabled=False,
            verification_enabled=True,
        )
        with patch("app.execution.contracts.runtime_service.generate", return_value=mock_resp):
            res = amof_supervisor.run(db=db, context=context)
        assert res.status == "COMPLETED", res.answer
    finally:
        db.close()

    event_types = [fields["event_type"] for _id, fields in fake.entries]
    assert "agent_started" in event_types
    assert "agent_completed" in event_types
    assert "verification_completed" in event_types
