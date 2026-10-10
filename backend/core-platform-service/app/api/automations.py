"""
Automation API Router (AMOF-X Phase 8). CRUD only -- the actual scheduled/
event-triggered run mechanism is Celery Beat + app/workers/tasks.py, not
this router. A manual "run now" endpoint is included for testing/debugging
without waiting on real Beat timing.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from pydantic import BaseModel, Field

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.automation import AutomationCreate, AutomationResponse, AutomationRunResult, AutomationUpdate
from app.services.automation_nl_parser import AutomationDraft, automation_nl_parser
from app.services.automation_service import DIGEST_DEFAULT_CRON, automation_service


class AutomationTextRequest(BaseModel):
    text: str = Field(..., min_length=1, description="e.g. 'Every Friday at 5 PM, send me a summary of overdue tasks'")

router = APIRouter(prefix="/automations", tags=["Automations"])


@router.post("", response_model=AutomationResponse, status_code=status.HTTP_201_CREATED)
def create_automation(
    data: AutomationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        automation = automation_service.create_automation(
            db=db,
            owner_id=str(current_user.id),
            name=data.name,
            trigger_type=data.trigger_type,
            steps=data.steps,
            schedule=data.schedule,
            condition=data.condition,
            enabled=data.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return automation_service.to_response_dto(automation)


@router.get("", response_model=list[AutomationResponse])
def list_automations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    automations = automation_service.list_automations(db=db, owner_id=str(current_user.id))
    return [automation_service.to_response_dto(a) for a in automations]


# Declared before /{automation_id}: FastAPI matches in definition order, so
# a literal "digest"/"from-text"/"reports" path registered after the
# parameterised route would be swallowed by it and arrive as
# automation_id="digest".
@router.post("/from-text", response_model=AutomationDraft)
def draft_automation_from_text(
    data: AutomationTextRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Phase 17: translate a sentence into a *draft* AutomationCreate for the
    caller to confirm. Deliberately creates nothing -- the confirmed draft
    is posted back to POST /automations like any other automation, so the
    NL path shares one creation path and one set of validations with the
    structured path rather than becoming a privileged shortcut.
    """
    return automation_nl_parser.parse(data.text, request_id=f"nlauto_{current_user.id}")


@router.get("/reports/latest")
def get_latest_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Phase 18 in-app delivery: the caller's most recent completed
    scheduled database report, read back from its Execution row."""
    report = automation_service.latest_report(db=db, owner_id=str(current_user.id))
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No scheduled report has run yet")
    return report



@router.post("/digest/enable", response_model=AutomationResponse)
def enable_daily_digest(
    schedule: str = DIGEST_DEFAULT_CRON,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Phase 16 opt-in. Idempotent: repeat calls re-enable the caller's
    existing digest rather than creating a second one."""
    automation = automation_service.enable_daily_digest(
        db=db, owner_id=str(current_user.id), schedule=schedule,
    )
    return automation_service.to_response_dto(automation)


@router.get("/digest/latest")
def get_latest_digest(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """In-app delivery: the caller's most recent completed digest, read back
    from the execution record the scheduled run persists."""
    digest = automation_service.latest_digest(db=db, owner_id=str(current_user.id))
    if not digest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No digest has been generated yet")
    return digest


@router.post("/digest/run-now")
def run_digest_now(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Morning Brief "Generate now": finds-or-creates the caller's Daily Digest
    automation (enable_daily_digest is idempotent by name) and runs it
    synchronously through the same automation_service.run_automation() ->
    amof_supervisor.run(preset_plan=...) path Celery Beat uses, so this adds
    no second dispatch path -- just a manual trigger for the existing one.
    """
    owner_id = str(current_user.id)
    automation = automation_service.enable_daily_digest(db=db, owner_id=owner_id)
    automation_service.run_automation(db, automation)
    digest = automation_service.latest_digest(db=db, owner_id=owner_id)
    if not digest:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Digest run did not produce a result")
    return digest


@router.post("/digest/disable", response_model=AutomationResponse)
def disable_daily_digest(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    automation = automation_service.disable_daily_digest(db=db, owner_id=str(current_user.id))
    if not automation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No daily digest automation to disable")
    return automation_service.to_response_dto(automation)


@router.get("/{automation_id}", response_model=AutomationResponse)
def get_automation(
    automation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    automation = automation_service.get_automation(db=db, owner_id=str(current_user.id), automation_id=automation_id)
    if not automation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Automation '{automation_id}' not found or access denied")
    return automation_service.to_response_dto(automation)


@router.patch("/{automation_id}", response_model=AutomationResponse)
def update_automation(
    automation_id: str,
    data: AutomationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    automation = automation_service.update_automation(
        db=db, owner_id=str(current_user.id), automation_id=automation_id,
        **data.model_dump(exclude_unset=True),
    )
    if not automation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Automation '{automation_id}' not found or access denied")
    return automation_service.to_response_dto(automation)


@router.post("/{automation_id}/run", response_model=AutomationRunResult)
def run_automation_now(
    automation_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Runs the automation synchronously, in-request -- a manual trigger for
    testing/debugging, not the production path (that's Celery Beat calling
    run_automation_task on its own schedule). Goes through the exact same
    automation_service.run_automation() -> amof_supervisor.run(preset_plan=...)
    path either way, so the approval gate applies identically.
    """
    automation = automation_service.get_automation(db=db, owner_id=str(current_user.id), automation_id=automation_id)
    if not automation:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Automation '{automation_id}' not found or access denied")
    if not automation.enabled:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Automation is disabled")

    response = automation_service.run_automation(db, automation)
    return AutomationRunResult(
        automation_id=automation_id,
        request_id=response.request_id,
        status=response.status,
        approval_id=response.approval_id,
    )
