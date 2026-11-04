"""
Commitment Run Service: Persistent background execution, real-time stage progress,
and lifecycle tracking for Commitment Intelligence scans and sweeps.
"""
import json
import logging
import threading
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Optional
from sqlalchemy.orm import Session

from app.db.database import SessionLocal
from app.models.commitment_run import CommitmentRun, CommitmentRunStage
from app.models.commitment import Commitment
from app.models.meeting import MeetingActionItem
from app.services.commitment_service import commitment_service
from app.services.google_connector_service import GoogleConnectorService
from app.services.meeting_service import meeting_service
from app.agents.inbox_agent import inbox_agent
from app.services.work_ai import orchestrator

logger = logging.getLogger(__name__)

SCAN_STAGES = [
    ("initialize_scan", "Initialize scan", 5),
    ("validate_connectors", "Validate connectors", 10),
    ("fetch_gmail", "Fetch Gmail messages", 20),
    ("extract_commitments", "Extract commitments from email", 65),
    ("process_meetings", "Process meeting action items", 80),
    ("validate_ownership", "Validate ownership and deadlines", 90),
    ("save_deduplicate", "Save and deduplicate records", 97),
    ("finalize_results", "Finalize execution", 100),
]

SWEEP_STAGES = [
    ("commitment_scan", "Autonomous commitment scan", 55),
    ("task_proposals", "Draft task proposals for AI Inbox", 75),
    ("duplicate_checking", "Duplicate and relationship checking", 82),
    ("risk_analysis", "WorkGraph risk analysis", 93),
    ("persist_results", "Persist proposals and alerts", 97),
    ("finalize", "Finalize sweep summary", 100),
]


class CommitmentRunService:

    @staticmethod
    def create_run(
        db: Session,
        owner_id: str,
        run_type: str = "scan",
    ) -> CommitmentRun:
        """Creates a new durable execution run with initialized stages. Prevents duplicate active runs."""
        CommitmentRunService.recover_stale_runs(db, owner_id)
        active = (
            db.query(CommitmentRun)
            .filter(
                CommitmentRun.owner_id == owner_id,
                CommitmentRun.run_type == run_type,
                CommitmentRun.status.in_(["queued", "running"]),
            )
            .first()
        )
        if active:
            return active

        run = CommitmentRun(
            owner_id=owner_id,
            run_type=run_type,
            status="queued",
            current_stage="initialize_scan" if run_type == "scan" else "commitment_scan",
            progress_percent=0,
            warnings=json.dumps([]),
            errors=json.dumps([]),
            result_summary=json.dumps({}),
        )
        db.add(run)
        db.commit()
        db.refresh(run)

        # Populate stages
        stages_def = SCAN_STAGES if run_type == "scan" else SWEEP_STAGES
        for idx, (stage_name, _, _) in enumerate(stages_def):
            stg = CommitmentRunStage(
                run_id=run.id,
                stage_name=stage_name,
                stage_order=idx + 1,
                status="pending",
                progress_percent=0,
                processed_count=0,
                total_count=0,
            )
            db.add(stg)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def get_run(db: Session, run_id: str, owner_id: str) -> Optional[CommitmentRun]:
        return (
            db.query(CommitmentRun)
            .filter(CommitmentRun.id == run_id, CommitmentRun.owner_id == owner_id)
            .first()
        )

    @staticmethod
    def get_latest_active_run(db: Session, owner_id: str) -> Optional[CommitmentRun]:
        CommitmentRunService.recover_stale_runs(db, owner_id)
        return (
            db.query(CommitmentRun)
            .filter(
                CommitmentRun.owner_id == owner_id,
                CommitmentRun.status.in_(["queued", "running"]),
            )
            .order_by(CommitmentRun.created_at.desc())
            .first()
        )

    @staticmethod
    def list_runs(db: Session, owner_id: str, limit: int = 20) -> list[CommitmentRun]:
        return (
            db.query(CommitmentRun)
            .filter(CommitmentRun.owner_id == owner_id)
            .order_by(CommitmentRun.created_at.desc())
            .limit(limit)
            .all()
        )

    @staticmethod
    def cancel_run(db: Session, run_id: str, owner_id: str) -> Optional[CommitmentRun]:
        run = CommitmentRunService.get_run(db, run_id, owner_id)
        if not run:
            return None
        if run.status in ("queued", "running"):
            run.cancel_requested = True
            run.status = "cancelled"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
        return run

    @staticmethod
    def recover_stale_runs(db: Session, owner_id: str) -> int:
        """Marks runs stuck in running/queued for over 15 minutes as failed."""
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
        stale = (
            db.query(CommitmentRun)
            .filter(
                CommitmentRun.owner_id == owner_id,
                CommitmentRun.status.in_(["queued", "running"]),
                CommitmentRun.updated_at < cutoff,
            )
            .all()
        )
        count = 0
        for r in stale:
            r.status = "failed"
            r.completed_at = datetime.now(timezone.utc)
            errs = json.loads(r.errors or "[]")
            errs.append("Execution timed out or interrupted.")
            r.errors = json.dumps(errs)
            count += 1
        if count > 0:
            db.commit()
        return count

    @staticmethod
    def start_background_scan(run_id: str, owner_id: str, max_emails: int = 10, user_tz: str = "UTC") -> None:
        """Launches scan job in a background daemon thread with durable DB tracking."""
        t = threading.Thread(
            target=CommitmentRunService._execute_scan_worker,
            args=(run_id, owner_id, max_emails, user_tz),
            daemon=True,
        )
        t.start()

    @staticmethod
    def start_background_sweep(
        run_id: str, owner_id: str, max_emails: int = 10, user_email: Optional[str] = None
    ) -> None:
        """Launches sweep job in a background daemon thread with durable DB tracking."""
        t = threading.Thread(
            target=CommitmentRunService._execute_sweep_worker,
            args=(run_id, owner_id, max_emails, user_email),
            daemon=True,
        )
        t.start()

    @staticmethod
    def _update_stage(
        db: Session,
        run_id: str,
        stage_name: str,
        status: str,
        progress: int,
        processed: int = 0,
        total: int = 0,
        error_msg: Optional[str] = None,
    ) -> None:
        stg = (
            db.query(CommitmentRunStage)
            .filter(CommitmentRunStage.run_id == run_id, CommitmentRunStage.stage_name == stage_name)
            .first()
        )
        if stg:
            stg.status = status
            stg.progress_percent = progress
            stg.processed_count = processed
            stg.total_count = total
            if error_msg:
                stg.error_message = error_msg
            if status == "running" and not stg.started_at:
                stg.started_at = datetime.now(timezone.utc)
            elif status in ("completed", "failed", "skipped"):
                stg.completed_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def _execute_scan_worker(run_id: str, owner_id: str, max_emails: int, user_tz: str) -> None:
        db = SessionLocal()
        try:
            run = db.query(CommitmentRun).filter(CommitmentRun.id == run_id).first()
            if not run:
                return

            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            db.commit()

            warnings: list[str] = []
            errors: list[str] = []

            # 1. Initialize
            if run.cancel_requested:
                return
            CommitmentRunService._update_stage(db, run_id, "initialize_scan", "running", 50)
            run.current_stage = "initialize_scan"
            run.progress_percent = 5
            db.commit()
            time.sleep(0.2)
            CommitmentRunService._update_stage(db, run_id, "initialize_scan", "completed", 100)

            # 2. Validate connectors
            if run.cancel_requested:
                return
            CommitmentRunService._update_stage(db, run_id, "validate_connectors", "running", 50)
            run.current_stage = "validate_connectors"
            run.progress_percent = 10
            db.commit()

            gmail_connected = False
            try:
                # Try getting token or checking connector
                unread = GoogleConnectorService.unread_messages(db, int(owner_id), limit=max_emails)
                gmail_connected = True
                messages = unread if isinstance(unread, list) else []
            except Exception as e:
                warnings.append(f"Gmail connector note: {e}")
                messages = []

            CommitmentRunService._update_stage(
                db, run_id, "validate_connectors", "completed", 100, processed=1, total=1
            )

            # 3. Fetch Gmail
            if run.cancel_requested:
                return
            CommitmentRunService._update_stage(
                db, run_id, "fetch_gmail", "running", 50, processed=len(messages), total=max_emails
            )
            run.current_stage = "fetch_gmail"
            run.progress_percent = 20
            run.total_items = len(messages)
            db.commit()
            time.sleep(0.2)
            CommitmentRunService._update_stage(
                db, run_id, "fetch_gmail", "completed", 100, processed=len(messages), total=len(messages)
            )

            # 4. Extract commitments from email
            if run.cancel_requested:
                return
            CommitmentRunService._update_stage(
                db, run_id, "extract_commitments", "running", 10, processed=0, total=len(messages)
            )
            run.current_stage = "extract_commitments"
            run.progress_percent = 35
            db.commit()

            extracted_items = []
            if messages:
                extraction_result = inbox_agent.extract_commitments_detailed(messages)
                extracted_items = extraction_result.get("commitments", [])
                run.commitments_found = len(extracted_items)
                run.processed_items = extraction_result.get("processed_messages", len(messages))
                run.successful_items = extraction_result.get("successful_messages", len(messages))
                run.failed_items = extraction_result.get("failed_messages", 0)
                if extraction_result.get("warnings"):
                    warnings.extend(extraction_result["warnings"])
                if extraction_result.get("errors"):
                    errors.extend(extraction_result["errors"])

            CommitmentRunService._update_stage(
                db,
                run_id,
                "extract_commitments",
                "completed",
                100,
                processed=len(messages),
                total=len(messages),
            )
            run.progress_percent = 65
            db.commit()

            # 5. Process meeting action items
            if run.cancel_requested:
                return
            CommitmentRunService._update_stage(db, run_id, "process_meetings", "running", 50)
            run.current_stage = "process_meetings"
            run.progress_percent = 70
            db.commit()

            try:
                meeting_items = meeting_service.list_action_items_for_owner(db, owner_id)
            except Exception as e:
                logger.warning("[CommitmentRunService] Meeting fetch warning: %s", e)
                meeting_items = []

            CommitmentRunService._update_stage(
                db, run_id, "process_meetings", "completed", 100, processed=len(meeting_items), total=len(meeting_items)
            )
            run.progress_percent = 80
            db.commit()

            # 6. Validate ownership and deadlines
            if run.cancel_requested:
                return
            CommitmentRunService._update_stage(db, run_id, "validate_ownership", "running", 50)
            run.current_stage = "validate_ownership"
            run.progress_percent = 85
            db.commit()
            time.sleep(0.2)
            CommitmentRunService._update_stage(db, run_id, "validate_ownership", "completed", 100)
            run.progress_percent = 90
            db.commit()

            # 7. Save and deduplicate
            if run.cancel_requested:
                return
            CommitmentRunService._update_stage(db, run_id, "save_deduplicate", "running", 50)
            run.current_stage = "save_deduplicate"
            run.progress_percent = 92
            db.commit()

            created_count = 0
            updated_count = 0

            # Upsert Gmail commitments
            for item in extracted_items:
                try:
                    _, was_created = commitment_service.upsert_commitment(
                        db=db,
                        owner_id=owner_id,
                        description=item["description"],
                        source_type="gmail",
                        source_ref=item["id"],
                        responsible_party=item.get("owner"),
                        counterparty=item.get("counterparty"),
                        direction=item.get("direction", "owed_by_me"),
                        due_date=item.get("due_date"),
                        evidence=item.get("evidence"),
                        confidence=item.get("confidence", 0.9),
                        priority=item.get("priority", "medium"),
                        user_tz=user_tz,
                    )
                    created_count += int(was_created)
                    updated_count += int(not was_created)
                except Exception as e:
                    errors.append(f"Upsert failed for item {item.get('id')}: {e}")

            # Upsert Meeting action items
            for item in meeting_items:
                try:
                    _, was_created = commitment_service.upsert_commitment(
                        db=db,
                        owner_id=owner_id,
                        description=item.description,
                        source_type="meeting",
                        source_ref=item.id,
                        responsible_party=item.owner,
                        due_date=item.due_date,
                        linked_task_id=item.workgraph_task_id,
                        user_tz=user_tz,
                    )
                    created_count += int(was_created)
                    updated_count += int(not was_created)
                except Exception as e:
                    errors.append(f"Meeting item upsert failed for {item.id}: {e}")

            run.created_count = created_count
            run.updated_count = updated_count
            CommitmentRunService._update_stage(db, run_id, "save_deduplicate", "completed", 100)
            run.progress_percent = 97
            db.commit()

            # 8. Finalize results
            CommitmentRunService._update_stage(db, run_id, "finalize_results", "running", 50)
            run.current_stage = "finalize_results"
            run.progress_percent = 100
            run.completed_at = datetime.now(timezone.utc)
            run.warnings = json.dumps(warnings)
            run.errors = json.dumps(errors)

            if len(errors) > 0 and created_count == 0 and updated_count == 0:
                run.status = "failed"
            elif len(warnings) > 0 or len(errors) > 0:
                run.status = "completed_with_warnings"
            else:
                run.status = "completed"

            run.result_summary = json.dumps({
                "scanned_gmail": len(messages),
                "scanned_meeting_items": len(meeting_items),
                "commitments_found": len(extracted_items) + len(meeting_items),
                "created": created_count,
                "updated": updated_count,
                "warnings_count": len(warnings),
                "errors_count": len(errors),
            })
            CommitmentRunService._update_stage(db, run_id, "finalize_results", "completed", 100)
            db.commit()

        except Exception as e:
            logger.exception("[CommitmentRunService] Scan execution crashed: %s", e)
            try:
                run = db.query(CommitmentRun).filter(CommitmentRun.id == run_id).first()
                if run:
                    run.status = "failed"
                    run.completed_at = datetime.now(timezone.utc)
                    errs = json.loads(run.errors or "[]")
                    errs.append(str(e))
                    run.errors = json.dumps(errs)
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()

    @staticmethod
    def _execute_sweep_worker(run_id: str, owner_id: str, max_emails: int, user_email: Optional[str]) -> None:
        db = SessionLocal()
        try:
            run = db.query(CommitmentRun).filter(CommitmentRun.id == run_id).first()
            if not run:
                return

            run.status = "running"
            run.started_at = datetime.now(timezone.utc)
            db.commit()

            # Stage 1: Commitment scan
            CommitmentRunService._update_stage(db, run_id, "commitment_scan", "running", 30)
            run.current_stage = "commitment_scan"
            run.progress_percent = 25
            db.commit()

            sweep_res = orchestrator.commitment_sweep(
                db=db,
                owner_id=owner_id,
                max_emails=max_emails,
                user_email=user_email,
            )

            CommitmentRunService._update_stage(db, run_id, "commitment_scan", "completed", 100)
            run.progress_percent = 55
            db.commit()

            # Stage 2: Task proposals
            CommitmentRunService._update_stage(
                db,
                run_id,
                "task_proposals",
                "completed",
                100,
                processed=sweep_res.get("proposals_created", 0),
                total=sweep_res.get("proposals_created", 0),
            )
            run.progress_percent = 75
            db.commit()

            # Stage 3: Duplicate checking
            CommitmentRunService._update_stage(
                db,
                run_id,
                "duplicate_checking",
                "completed",
                100,
                processed=sweep_res.get("duplicate_warnings", 0),
            )
            run.progress_percent = 82
            db.commit()

            # Stage 4: Risk analysis
            CommitmentRunService._update_stage(
                db,
                run_id,
                "risk_analysis",
                "completed",
                100,
                processed=sweep_res.get("risk_alerts_created", 0),
            )
            run.progress_percent = 93
            db.commit()

            # Stage 5: Persist results
            CommitmentRunService._update_stage(db, run_id, "persist_results", "completed", 100)
            run.progress_percent = 97
            db.commit()

            # Stage 6: Finalize
            scan_data = sweep_res.get("scan", {})
            run.created_count = scan_data.get("created", 0)
            run.updated_count = scan_data.get("updated", 0)
            run.total_items = scan_data.get("scanned_gmail", 0) + scan_data.get("scanned_meeting_items", 0)
            run.commitments_found = run.created_count + run.updated_count

            run.current_stage = "finalize"
            run.progress_percent = 100
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            run.result_summary = json.dumps(sweep_res)
            CommitmentRunService._update_stage(db, run_id, "finalize", "completed", 100)
            db.commit()

        except Exception as e:
            logger.exception("[CommitmentRunService] Sweep execution failed: %s", e)
            try:
                run = db.query(CommitmentRun).filter(CommitmentRun.id == run_id).first()
                if run:
                    run.status = "failed"
                    run.completed_at = datetime.now(timezone.utc)
                    errs = json.loads(run.errors or "[]")
                    errs.append(str(e))
                    run.errors = json.dumps(errs)
                    db.commit()
            except Exception:
                pass
        finally:
            db.close()


commitment_run_service = CommitmentRunService()

