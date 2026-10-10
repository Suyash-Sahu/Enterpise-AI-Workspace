"""
Event publisher (AMOF-X Phase 8): pushes Event rows to a Redis Stream via
XADD, reusing app/cache/client.py's existing RedisClient rather than
opening a second Redis connection (same reasoning as app/services/
calendar_service.py reusing TokenService instead of a second token path).

Degrades the same way the rest of app/cache/ already documents doing: a
missing/unreachable Redis logs and no-ops, never raises into the caller --
an instrumentation call site (e.g. a step inside AMOFSupervisor.run())
must never fail the actual request because the event bus is down.
"""
import logging
from typing import Optional

from app.cache.client import redis_client
from app.events.schema import Event

logger = logging.getLogger(__name__)

STREAM_KEY = "amofx:events"


class EventPublisher:

    def publish(self, event: Event) -> Optional[str]:
        client = redis_client.get_raw_client()
        if client is None:
            logger.info(
                "[EventPublisher] Redis unavailable; dropping event '%s' (degraded mode, same as app/cache).",
                event.event_type.value,
            )
            return None
        try:
            return client.xadd(
                STREAM_KEY,
                {
                    "event_type": event.event_type.value,
                    "owner_id": event.owner_id or "",
                    "trace_id": event.trace_id or "",
                    "data": event.model_dump_json(),
                },
            )
        except Exception:
            logger.exception("[EventPublisher] XADD failed for event '%s'", event.event_type.value)
            return None


event_publisher = EventPublisher()
