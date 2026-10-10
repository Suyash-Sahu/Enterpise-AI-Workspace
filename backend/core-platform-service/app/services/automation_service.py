"""
Automation service (AMOF-X Phase 8): CRUD over Automation rows, building a
real SupervisorPlan from a stored template and running it through
AMOFSupervisor.run(preset_plan=...) -- the exact same approval-gated
dispatch path an interactive request uses (see supervisor.py's `run()`
docstring). This is what makes "no automation-only bypass" a structural
fact rather than a policy statement: run_automation() has no code path
that skips _dispatch_step's approval check.
"""
import json
import logging
from typing import Any, Optional
from sqlalchemy.orm import Session

from celery.schedules import crontab

from app.models.automation import Automation
from app.models.execution import Execution
from app.schemas.automation import AutomationResponse, AutomationStep
from app.schemas.supervisor import PlanStep, SupervisorPlan, SupervisorResponse
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor

logger = logging.getLogger(__name__)

RUN_AUTOMATION_TASK_NAME = "app.workers.tasks.run_automation_task"

# Phase 16 digest opt-in. The name is the idempotency key for
# enable_daily_digest -- one digest automation per owner, by construction.
DIGEST_AUTOMATION_NAME = "Daily Digest"
DIGEST_CAPABILITY = "digest.daily"
DIGEST_DEFAULT_CRON = "0 8 * * *"  # 08:00 daily

# Phase 18 scheduled database report. Read-only capability, so a scheduled
# run completes outright rather than parking on an approval.
REPORT_CAPABILITY = "database_report"


def _parse_cron(cron_string: str) -> crontab:
    """
    "minute hour day_of_month month_of_year day_of_week", the standard
    5-field cron layout -- Celery's crontab() wants those as separate
    kwargs, not a raw string.
    """
    parts = cron_string.split()
    if len(parts) != 5:
        raise ValueError(f"Cron string {cron_string!r} must have exactly 5 fields (minute hour dom month dow)")
    minute, hour, day_of_month, month_of_year, day_of_week = parts
    return crontab(
        minute=minute, hour=hour,
        day_of_month=day_of_month, month_of_year=month_of_year, day_of_week=day_of_week,
    )


class AutomationService:

    @staticmethod
    def create_automation(
        db: Session,
        owner_id: str,
        name: str,
        trigger_type: str,
        steps: list[AutomationStep],
        schedule: Optional[str] = None,
        condition: Optional[dict[str, Any]] = None,
        enabled: bool = True,
    ) -> Automation:
        if trigger_type == "schedule" and not schedule:
            raise ValueError("trigger_type='schedule' requires a 'schedule' cron string")
        if trigger_type in ("condition", "event") and not condition:
            raise ValueError(f"trigger_type={trigger_type!r} requires a 'condition' dict")

        automation = Automation(
            owner_id=owner_id,
            name=name,
            trigger_type=trigger_type,
            schedule=schedule,
            condition=json.dumps(condition) if condition else None,
            task_graph_template=json.dumps({"steps": [s.model_dump() for s in steps]}),
            enabled=enabled,
            execution_history=json.dumps([]),
        )
        db.add(automation)
        db.commit()
        db.refresh(automation)
        return automation

    @staticmethod
    def enable_daily_digest(
        db: Session,
        owner_id: str,
        schedule: str = DIGEST_DEFAULT_CRON,
    ) -> Automation:
        """
        Phase 16 opt-in toggle. Idempotent by (owner_id, name): opting in
        twice re-enables and re-schedules the existing row rather than
        creating a second automation, because two rows would mean two
        digests delivered every morning and nothing downstream would flag
        that as wrong.

        Uses the ordinary create_automation path -- no bespoke scheduling,
        so build_beat_schedule() picks this up at beat startup exactly like
        any other scheduled automation.
        """
        existing = (
            db.query(Automation)
            .filter(Automation.owner_id == owner_id, Automation.name == DIGEST_AUTOMATION_NAME)
            .first()
        )
        if existing:
            existing.schedule = schedule
            existing.enabled = True
            db.commit()
            db.refresh(existing)
            return existing

        return AutomationService.create_automation(
            db=db,
            owner_id=owner_id,
            name=DIGEST_AUTOMATION_NAME,
            trigger_type="schedule",
            schedule=schedule,
            steps=[AutomationStep(step_id="digest", capability=DIGEST_CAPABILITY, input_template={})],
        )

    @staticmethod
    def latest_result(db: Session, owner_id: str, capability: str) -> Optional[dict[str, Any]]:
        """
        In-app delivery: the most recent completed run of `capability` for
        this owner, read back from the Execution row the scheduled run
        already persists. Shared by the Phase 16 digest and the Phase 18
        scheduled database report.

        Deliberately not a new notifications table. The result is already
        durably recorded by the normal execution path, and a second copy
        would be a second source of truth to keep in sync -- the same
        duplicated-source-of-truth mistake build_beat_schedule avoids.

        Deliberately not emailed either: GmailSendHandler requires human
        approval by design, so an emailed digest/report would park every
        run on an approval prompt, and auto-sending it would mean an
        automation-only bypass of the approval gate -- which run_automation
        structurally refuses (see its docstring).

        The owner_id filter is what scopes delivery: another owner's run is
        not merely hidden from the response, it is never selected.
        """
        row = (
            db.query(Execution)
            .filter(
                Execution.owner_id == owner_id,
                Execution.task_type == capability,
                Execution.status == "COMPLETED",
            )
            .order_by(Execution.created_at.desc())
            .first()
        )
        if not row or not row.result_json:
            return None

        payload = json.loads(row.result_json) if isinstance(row.result_json, str) else row.result_json
        return {"execution_id": row.id, "completed_at": row.completed_at, "result": payload}

    @staticmethod
    def latest_digest(db: Session, owner_id: str) -> Optional[dict[str, Any]]:
        """Phase 16 Task 4 in-app delivery. Keeps the "digest" response key
        the existing endpoint and frontend already read."""
        delivered = AutomationService.latest_result(db, owner_id, DIGEST_CAPABILITY)
        if not delivered:
            return None
        return {
            "execution_id": delivered["execution_id"],
            "completed_at": delivered["completed_at"],
            "digest": delivered["result"],
        }

    @staticmethod
    def latest_report(db: Session, owner_id: str) -> Optional[dict[str, Any]]:
        """Phase 18 Task 4 in-app delivery of the scheduled database report."""
        return AutomationService.latest_result(db, owner_id, REPORT_CAPABILITY)

    @staticmethod
    def disable_daily_digest(db: Session, owner_id: str) -> Optional[Automation]:
        """Opt-out: disables rather than deletes, so the user's chosen
        schedule survives a toggle off/on."""
        existing = (
            db.query(Automation)
            .filter(Automation.owner_id == owner_id, Automation.name == DIGEST_AUTOMATION_NAME)
            .first()
        )
        if not existing:
            return None
        existing.enabled = False
        db.commit()
        db.refresh(existing)
        return existing

    @staticmethod
    def list_automations(db: Session, owner_id: str) -> list[Automation]:
        return (
            db.query(Automation)
            .filter(Automation.owner_id == owner_id)
            .order_by(Automation.created_at.desc())
            .all()
        )

    @staticmethod
    def get_automation(db: Session, owner_id: str, automation_id: str) -> Optional[Automation]:
        return (
            db.query(Automation)
            .filter(Automation.id == automation_id, Automation.owner_id == owner_id)
            .first()
        )

    @staticmethod
    def update_automation(
        db: Session,
        owner_id: str,
        automation_id: str,
        *,
        name: Optional[str] = None,
        schedule: Optional[str] = None,
        condition: Optional[dict[str, Any]] = None,
        steps: Optional[list[AutomationStep]] = None,
        enabled: Optional[bool] = None,
    ) -> Optional[Automation]:
        automation = AutomationService.get_automation(db, owner_id, automation_id)
        if not automation:
            return None
        if name is not None:
            automation.name = name
        if schedule is not None:
            automation.schedule = schedule
        if condition is not None:
            automation.condition = json.dumps(condition)
        if steps is not None:
            automation.task_graph_template = json.dumps({"steps": [s.model_dump() for s in steps]})
        if enabled is not None:
            automation.enabled = enabled
        db.commit()
        db.refresh(automation)
        return automation

    @staticmethod
    def to_response_dto(automation: Automation) -> AutomationResponse:
        template = json.loads(automation.task_graph_template)
        return AutomationResponse(
            id=automation.id,
            owner_id=automation.owner_id,
            name=automation.name,
            trigger_type=automation.trigger_type,
            schedule=automation.schedule,
            condition=json.loads(automation.condition) if automation.condition else None,
            steps=[AutomationStep(**s) for s in template.get("steps", [])],
            enabled=automation.enabled,
            execution_history=json.loads(automation.execution_history) if automation.execution_history else [],
            created_at=automation.created_at,
            updated_at=automation.updated_at,
        )

    @staticmethod
    def _record_run(db: Session, automation: Automation, response: SupervisorResponse) -> None:
        history = json.loads(automation.execution_history) if automation.execution_history else []
        history.append({
            "request_id": response.request_id,
            "status": response.status,
            "execution_time": response.execution_time,
            "approval_id": response.approval_id,
        })
        automation.execution_history = json.dumps(history[-50:])  # bounded, not unbounded growth
        db.commit()

    @staticmethod
    def run_automation(db: Session, automation: Automation) -> SupervisorResponse:
        """
        Builds a real SupervisorPlan from the stored template and dispatches
        it through amof_supervisor.run(preset_plan=...) -- if a step
        resolves to a side-effecting capability, this creates a pending
        Approval and returns WAITING_FOR_APPROVAL exactly like an
        interactive request would, it does not execute it.
        """
        template = json.loads(automation.task_graph_template)
        plan_steps = [PlanStep(**s) for s in template.get("steps", [])]

        context = SupervisorContext(
            owner_id=automation.owner_id,
            question=f"[automation] {automation.name}",
        )
        preset_plan = SupervisorPlan(
            plan_id=f"autoplan_{automation.id}_{context.request_id[-8:]}",
            request_id=context.request_id,
            steps=plan_steps,
        )

        response = amof_supervisor.run(db=db, context=context, preset_plan=preset_plan)
        AutomationService._record_run(db, automation, response)
        return response

    @staticmethod
    def build_beat_schedule(db: Session) -> dict:
        """
        Populates Celery's beat_schedule from enabled trigger_type="schedule"
        rows -- read at worker/beat startup, never hand-maintained separately
        from the DB (the same duplicated-source-of-truth mistake already
        fixed for ACTION_POLICIES/ALLOWED_CAPABILITIES/the SENSITIVE set
        earlier in this project).
        """
        schedule: dict[str, dict] = {}
        rows = (
            db.query(Automation)
            .filter(Automation.trigger_type == "schedule", Automation.enabled.is_(True))
            .all()
        )
        for automation in rows:
            if not automation.schedule:
                continue
            try:
                schedule[f"automation-{automation.id}"] = {
                    "task": RUN_AUTOMATION_TASK_NAME,
                    "schedule": _parse_cron(automation.schedule),
                    "args": (automation.id,),
                }
            except ValueError:
                logger.warning("[AutomationService] Skipping automation %s: invalid cron %r", automation.id, automation.schedule)
        return schedule

    @staticmethod
    def find_condition_matches(db: Session, event_type: str, owner_id: Optional[str] = None) -> list[Automation]:
        """Enabled condition/event automations whose stored condition's
        event_type matches the given event. Matching is intentionally
        simple (event_type equality) -- condition is a JSON dict so richer
        matching can be added later without a schema change."""
        query = db.query(Automation).filter(
            Automation.trigger_type.in_(["condition", "event"]),
            Automation.enabled.is_(True),
        )
        if owner_id is not None:
            query = query.filter(Automation.owner_id == owner_id)

        matches = []
        for automation in query.all():
            if not automation.condition:
                continue
            try:
                cond = json.loads(automation.condition)
            except json.JSONDecodeError:
                continue
            if cond.get("event_type") == event_type:
                matches.append(automation)
        return matches


automation_service = AutomationService()
