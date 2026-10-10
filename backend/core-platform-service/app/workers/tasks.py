"""
Celery tasks (AMOF-X Phase 8). Each task opens its own DB session -- a
worker process has no request-scoped session to reuse -- and always closes
it in a finally block, matching the SessionLocal()/try/finally pattern
already used throughout this codebase's service layer.
"""
import logging

from app.db.database import SessionLocal
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)

_LAST_CONSUMED_ID_KEY = "amofx:events:last_consumed_id"


@celery_app.task(name="app.workers.tasks.sync_drive_task")
def sync_drive_task(owner_id: str) -> dict:
    """
    Pulls the authenticated user's Drive files and ingests each into the RAG
    pipeline. No request-triggered Drive-sync path exists yet to "move" here
    (a pre-existing, separately-documented gap -- CURRENT_STATE.md §7), so
    this is genuinely new work, not a relocation.

    Fetches real content directly via GoogleConnectorService and passes it
    into rag_pipeline.ingest(text=...), rather than going through
    RAGPipeline._fetch_from_google_connector -- that helper calls
    GoogleConnectorService.list_drive_files()/.get_file_content() with the
    wrong signature (missing db/user_id; get_file_content doesn't exist at
    all), so it always raises internally and falls through to a hardcoded
    placeholder string. That bug is real, pre-existing, and out of this
    phase's scope to fix (it also affects DocumentSummaryHandler's file_id
    path in app/execution/contracts.py) -- flagged for the user, not
    inherited into a new scheduled task.
    """
    from app.rag.pipeline import rag_pipeline
    from app.services.google_connector_service import GoogleConnectorService

    db = SessionLocal()
    try:
        user_id = int(owner_id)
        files = GoogleConnectorService.list_drive_files(db=db, user_id=user_id)
        results = []
        for f in files:
            file_id = f.get("id")
            if not file_id:
                continue
            try:
                raw = GoogleConnectorService.download_drive_file(db=db, user_id=user_id, file_id=file_id)
                text = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else str(raw)
                if not text.strip():
                    # Binary download came back empty -- likely a native
                    # Google Doc, which download_file can't read; export
                    # it as plain text instead.
                    text = GoogleConnectorService.export_google_doc(db=db, user_id=user_id, file_id=file_id)
                res = rag_pipeline.ingest(db=db, file_id=file_id, source=f.get("name", file_id), owner_id=owner_id, text=text)
                results.append({"file_id": file_id, "status": "ingested", "chunks": res.chunk_count})
            except Exception as exc:
                logger.warning("[sync_drive_task] Failed to ingest file %s for owner %s: %s", file_id, owner_id, exc)
                results.append({"file_id": file_id, "status": "failed", "error": str(exc)})
        return {"owner_id": owner_id, "synced": len(results), "results": results}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.generate_embedding_task")
def generate_embedding_task(chunk_id: int) -> dict:
    """Regenerates and stores the embedding for one existing DocumentChunk."""
    from app.models.document_chunk import DocumentChunk
    from app.rag.embeddings import embedding_service

    db = SessionLocal()
    try:
        chunk = db.query(DocumentChunk).filter(DocumentChunk.id == chunk_id).first()
        if not chunk:
            return {"chunk_id": chunk_id, "status": "not_found"}
        vector = embedding_service.generate_embedding(chunk.text)
        chunk.set_vector(vector)
        db.commit()
        return {"chunk_id": chunk_id, "status": "embedded"}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.process_meeting_task")
def process_meeting_task(meeting_id: str) -> dict:
    """Runs extraction for an already-persisted (pending) Meeting row."""
    from app.agents.meeting_agent import meeting_agent
    from app.models.meeting import Meeting
    from app.services.meeting_service import meeting_service

    db = SessionLocal()
    try:
        meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not meeting:
            return {"meeting_id": meeting_id, "status": "not_found"}
        extraction = meeting_agent.extract(meeting.transcript_text)
        meeting_service.store_extraction(db, meeting, extraction)
        return {"meeting_id": meeting_id, "status": "processed"}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.run_automation_task")
def run_automation_task(automation_id: str) -> dict:
    """
    Dispatches one Automation through automation_service.run_automation(),
    which itself goes through amof_supervisor.run(preset_plan=...) -- the
    same approval-gated path an interactive request uses. Never a shortcut.
    """
    from app.models.automation import Automation
    from app.services.automation_service import automation_service

    db = SessionLocal()
    try:
        automation = db.query(Automation).filter(Automation.id == automation_id).first()
        if not automation:
            return {"automation_id": automation_id, "status": "not_found"}
        if not automation.enabled:
            return {"automation_id": automation_id, "status": "disabled"}

        response = automation_service.run_automation(db, automation)
        return {
            "automation_id": automation_id,
            "status": response.status,
            "request_id": response.request_id,
            "approval_id": response.approval_id,
        }
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.work_automations_tick_task")
def work_automations_tick_task() -> dict:
    """
    One evaluation pass over every active AMOF Work rule. Rules only ever emit
    AI proposals (never direct writes) and enforce their own kill switch,
    blast-radius, rate-limit and loop guards -- see work_ai/automations.py.
    """
    from app.services.work_ai import automations

    db = SessionLocal()
    try:
        return automations.tick(db)
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.poll_condition_automations_task")
def poll_condition_automations_task() -> dict:
    """
    One non-blocking pass over the event stream (app/events/publisher.py),
    triggering any enabled condition/event automation whose stored
    condition's event_type matches an event seen since the last poll.
    Intended to run on Celery Beat's own schedule (e.g. every 30s) rather
    than a long-lived blocking XREAD loop, which doesn't fit Celery's
    task model.
    """
    from app.cache.client import redis_client
    from app.events.publisher import STREAM_KEY
    from app.services.automation_service import automation_service

    client = redis_client.get_raw_client()
    if client is None:
        return {"status": "redis_unavailable"}

    last_id = client.get(_LAST_CONSUMED_ID_KEY) or "0"
    range_min = f"({last_id}" if last_id != "0" else "-"
    entries = client.xrange(STREAM_KEY, min=range_min, max="+", count=200)
    if not entries:
        return {"status": "no_new_events", "checked": 0, "triggered": 0}

    db = SessionLocal()
    triggered = 0
    try:
        for _entry_id, fields in entries:
            event_type = fields.get("event_type")
            owner_id = fields.get("owner_id") or None
            if not event_type:
                continue
            for automation in automation_service.find_condition_matches(db, event_type=event_type, owner_id=owner_id):
                run_automation_task.delay(automation.id)
                triggered += 1
        client.set(_LAST_CONSUMED_ID_KEY, entries[-1][0])
    finally:
        db.close()

    return {"status": "ok", "checked": len(entries), "triggered": triggered}
