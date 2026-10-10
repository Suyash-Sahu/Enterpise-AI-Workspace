"""
Celery app (AMOF-X Phase 8): broker/result backend is the same Redis
instance app/cache/ and app/events/publisher.py already talk to
(settings.REDIS_URL) -- not a second Redis dependency, per this phase's own
"read from app/core/config.py settings, don't hardcode a second URL" rule.
"""
from celery import Celery
from celery.schedules import schedule as celery_schedule
from celery.signals import beat_init

from app.core.config import settings

celery_app = Celery(
    "amofx",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Automation entries are populated into this at Beat startup (see
    # _load_dynamic_beat_schedule below) from enabled Automation rows --
    # never hand-maintained here, that would be the same duplicated-
    # schedule mistake this project has already fixed for policy dicts
    # three times this session. "poll-condition-automations" is the one
    # static entry: it exists regardless of DB content, since it's what
    # makes condition/event-triggered automations reachable at all.
    beat_schedule={
        "poll-condition-automations": {
            "task": "app.workers.tasks.poll_condition_automations_task",
            "schedule": celery_schedule(30.0),
        },
        # AMOF Work rule-based automations: one tick evaluates every active rule
        # (time- and activity-log-based triggers; see services/work_ai/automations.py).
        "work-automations-tick": {
            "task": "app.workers.tasks.work_automations_tick_task",
            "schedule": celery_schedule(60.0),
        },
    },
)


@beat_init.connect
def _load_dynamic_beat_schedule(sender=None, **kwargs):
    """Merges enabled trigger_type="schedule" Automation rows into the beat
    schedule at Beat-process startup, read fresh from the DB each time."""
    from app.db.database import SessionLocal
    from app.services.automation_service import automation_service

    db = SessionLocal()
    try:
        dynamic = automation_service.build_beat_schedule(db)
    finally:
        db.close()

    celery_app.conf.beat_schedule = {**celery_app.conf.beat_schedule, **dynamic}
