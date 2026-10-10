"""
Phase 24: Run Blackboard -- shared, owner-scoped working memory for one
orchestration run.

Before this, `SupervisorPlanner.resolve_step_input` supported exactly three
references (`$context.question`, `$context.file_id`, `$step.X.result`): a
step could only see the context or a direct dependency's result, nothing
accumulated across the run, and nothing survived a replan. `RunBlackboard`
adds a fourth, `$state.<key>` (see `app/supervisor/planner.py`), backed by
`AgentStateEntry` (`app/models/agent_state.py`).

Two invariants enforced here, for real, not just documented:
1. Every value written must already be a validated Pydantic model instance
   -- `put()` on a raw dict/other value is a call-time `ValueError`, not a
   silently-accepted write.
2. This object is bound to exactly one `(run_id, owner_id)` pair at
   construction time. There is no method anywhere on this class that takes
   a different owner_id or run_id as an argument, so there is no path --
   accidental or otherwise -- to read another owner's or another run's
   state through it.
"""
import json
import logging
import threading
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.agent_state import AgentStateEntry

logger = logging.getLogger(__name__)


class BlackboardCapacityExceeded(RuntimeError):
    """
    Raised when a write would push this run's blackboard past its configured
    entry-count or byte-size cap. Deliberately a loud failure -- the phase
    requirement is that exceeding the cap fails the run, not that state gets
    silently truncated (which would make a later `get()` return an
    incomplete view without any signal that it happened).
    """


class RunBlackboard:
    def __init__(self, db: Session, run_id: str, owner_id: str):
        self.db = db
        self.run_id = run_id
        self.owner_id = owner_id
        self._lock = threading.Lock()

    def _own_entries_query(self, db_sess: Session | None = None):
        sess = db_sess or self.db
        return (
            sess.query(AgentStateEntry)
            .filter(
                AgentStateEntry.run_id == self.run_id,
                AgentStateEntry.owner_id == self.owner_id,
            )
        )

    def put(self, key: str, value: BaseModel, written_by: Optional[str] = None, db_sess: Session | None = None) -> None:
        """
        Append a new entry under `key`. Never overwrites a prior entry for
        the same key -- `history(key)` depends on every write surviving.
        Thread-safe atomic write using self._lock.
        """
        if not isinstance(value, BaseModel):
            raise ValueError(
                f"RunBlackboard.put(key={key!r}) received a {type(value).__name__}, "
                "not a validated Pydantic model instance. Only validated agent "
                "output models may be written to the blackboard."
            )

        serialized = value.model_dump_json()
        new_bytes = len(serialized.encode("utf-8"))

        sess = db_sess or self.db
        with self._lock:
            existing = self._own_entries_query(sess).all()
            existing_count = len(existing)
            existing_bytes = sum(len(e.value_json.encode("utf-8")) for e in existing)

            if existing_count + 1 > settings.BLACKBOARD_MAX_ENTRIES:
                raise BlackboardCapacityExceeded(
                    f"Run {self.run_id!r} blackboard would exceed "
                    f"{settings.BLACKBOARD_MAX_ENTRIES} entries (owner {self.owner_id!r})."
                )
            if existing_bytes + new_bytes > settings.BLACKBOARD_MAX_BYTES:
                raise BlackboardCapacityExceeded(
                    f"Run {self.run_id!r} blackboard would exceed "
                    f"{settings.BLACKBOARD_MAX_BYTES} bytes (owner {self.owner_id!r})."
                )

            entry = AgentStateEntry(
                run_id=self.run_id,
                owner_id=self.owner_id,
                key=key,
                value_json=serialized,
                written_by_step=written_by,
            )
            sess.add(entry)
            sess.commit()

    def get(self, key: str) -> Optional[Any]:
        """The most recently written value for `key`, or None if never written."""
        latest = (
            self._own_entries_query()
            .filter(AgentStateEntry.key == key)
            .order_by(AgentStateEntry.created_at.desc(), AgentStateEntry.id.desc())
            .first()
        )
        if latest is None:
            return None
        return json.loads(latest.value_json)

    def keys(self) -> list[str]:
        """Every distinct key ever written in this run, for this owner."""
        rows = self._own_entries_query().with_entities(AgentStateEntry.key).distinct().all()
        return sorted({r[0] for r in rows})

    def history(self, key: str) -> list[Any]:
        """Every value ever written under `key`, oldest first."""
        rows = (
            self._own_entries_query()
            .filter(AgentStateEntry.key == key)
            .order_by(AgentStateEntry.created_at.asc(), AgentStateEntry.id.asc())
            .all()
        )
        return [json.loads(r.value_json) for r in rows]
