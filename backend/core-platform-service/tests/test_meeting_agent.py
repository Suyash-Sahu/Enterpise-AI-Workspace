"""
AMOF-X Phase 7: MeetingAgent extraction + "meeting.extract" capability tests.

The LLM call is stubbed via monkeypatch, same as tests/test_decomposer.py --
deterministic, no live Ollama/LiteLLM dependency (this environment's local
Ollama is confirmed down, same pre-existing condition noted in every prior
phase this session). tests/test_meeting_prompt_injection.py separately
covers the prompt-injection-resistance requirement.
"""
import json

from app.agents import meeting_agent as meeting_agent_module
from app.agents.meeting_agent import meeting_agent
from app.db.database import SessionLocal
from app.schemas.execution import ExecutionRequest
from app.schemas.runtime import RuntimeGenerateResponse
from app.services.execution_manager import execution_manager
from app.services.meeting_service import meeting_service

API = "/api/v1/meetings"

SAMPLE_TRANSCRIPT = (
    "Alice: Let's finalize the Q4 launch date.\n"
    "Bob: I think we should target November 15th.\n"
    "Alice: Agreed, November 15th it is. Bob, can you own the marketing brief by next Friday?\n"
    "Bob: Sure, I'll have it done by next Friday.\n"
    "Alice: One risk -- we haven't confirmed the vendor contract yet.\n"
    "Bob: Also unclear who owns the legal review."
)

SAMPLE_EXTRACTION_JSON = json.dumps(
    {
        "summary": "The team finalized the Q4 launch date for November 15th and assigned the marketing brief.",
        "decisions": ["Launch date set to November 15th."],
        "action_items": [
            {"description": "Write the marketing brief", "owner": "Bob", "due_date": "next Friday"},
        ],
        "risks": ["Vendor contract not yet confirmed."],
        "unresolved_questions": ["Who owns the legal review?"],
    }
)


def _stub_response(completion: str) -> RuntimeGenerateResponse:
    return RuntimeGenerateResponse(completion=completion, provider="stub", model="stub", runtime="local")


def test_extraction_parses_summary_decisions_action_items_correctly(monkeypatch):
    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", lambda req: _stub_response(SAMPLE_EXTRACTION_JSON))

    result = meeting_agent.extract(SAMPLE_TRANSCRIPT)

    assert "November 15th" in result["summary"]
    assert result["decisions"] == ["Launch date set to November 15th."]
    assert len(result["action_items"]) == 1
    assert result["action_items"][0]["description"] == "Write the marketing brief"
    assert result["action_items"][0]["owner"] == "Bob"
    assert result["action_items"][0]["due_date"] == "next Friday"
    assert result["risks"] == ["Vendor contract not yet confirmed."]
    assert result["unresolved_questions"] == ["Who owns the legal review?"]


def test_transcript_is_classified_not_the_wrapper_prompt(monkeypatch):
    """
    Same discipline as DocumentSummaryHandler/TaskDecomposer: the privacy
    router must classify the real transcript content, not the delimiter
    wrapper/system-prompt instructions around it.
    """
    captured = {}

    def fake_generate(req):
        captured["metadata"] = req.metadata
        captured["prompt"] = req.prompt
        captured["system_prompt"] = req.system_prompt
        return _stub_response(SAMPLE_EXTRACTION_JSON)

    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", fake_generate)

    meeting_agent.extract(SAMPLE_TRANSCRIPT)

    assert captured["metadata"]["classification_content"] == SAMPLE_TRANSCRIPT
    assert "<untrusted_data" in captured["prompt"]
    assert SAMPLE_TRANSCRIPT in captured["prompt"]
    assert "DATA to extract from" in captured["system_prompt"]


def test_malformed_output_falls_back_to_empty_extraction(monkeypatch):
    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", lambda req: _stub_response("not json at all"))

    result = meeting_agent.extract(SAMPLE_TRANSCRIPT)

    assert result == {
        "summary": "", "decisions": [], "action_items": [], "risks": [], "unresolved_questions": [],
    }


def test_generation_failure_falls_back_to_empty_extraction(monkeypatch):
    def boom(req):
        raise RuntimeError("runtime unavailable")

    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", boom)

    result = meeting_agent.extract(SAMPLE_TRANSCRIPT)

    assert result["summary"] == ""
    assert result["action_items"] == []


def test_meeting_extract_capability_persists_meeting_and_action_items(monkeypatch, test_user):
    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", lambda req: _stub_response(SAMPLE_EXTRACTION_JSON))

    db = SessionLocal()
    try:
        owner_id = str(test_user.id)
        req = ExecutionRequest(
            task_type="meeting.extract",
            input={"transcript_text": SAMPLE_TRANSCRIPT, "transcript_source": "manual_paste"},
        )
        res = execution_manager.execute(db=db, request=req, owner_id=owner_id)
        assert res.status.value == "COMPLETED", res.error_message

        meeting_id = res.result["meeting_id"]
        meeting = meeting_service.get_meeting(db=db, owner_id=owner_id, meeting_id=meeting_id)
        assert meeting is not None
        assert meeting.status == "processed"
        assert "November 15th" in meeting.summary

        dto = meeting_service.to_response_dto(db, meeting)
        assert len(dto.action_items) == 1
        assert dto.action_items[0].description == "Write the marketing brief"
        assert dto.action_items[0].workgraph_task_id is None  # opt-in, not automatic
    finally:
        db.close()


def test_meeting_extract_requires_no_approval(monkeypatch):
    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", lambda req: _stub_response(SAMPLE_EXTRACTION_JSON))

    db = SessionLocal()
    try:
        req = ExecutionRequest(
            task_type="meeting.extract",
            input={"transcript_text": "Short transcript."},
            approval_id=None,
        )
        res = execution_manager.execute(db=db, request=req, owner_id="1")
        assert res.status.value == "COMPLETED", res.error_message
    finally:
        db.close()


def test_create_meeting_and_fetch_via_api(monkeypatch, auth_client):
    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", lambda req: _stub_response(SAMPLE_EXTRACTION_JSON))

    created = auth_client.post(API, json={"transcript_text": SAMPLE_TRANSCRIPT})
    assert created.status_code == 201, created.text
    meeting = created.json()
    assert meeting["status"] == "processed"
    assert len(meeting["action_items"]) == 1

    fetched = auth_client.get(f"{API}/{meeting['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == meeting["id"]


def test_action_item_opt_in_task_creation_creates_a_real_workgraph_task(monkeypatch, auth_client):
    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", lambda req: _stub_response(SAMPLE_EXTRACTION_JSON))

    created = auth_client.post(API, json={"transcript_text": SAMPLE_TRANSCRIPT}).json()
    item_id = created["action_items"][0]["id"]

    task_resp = auth_client.post(f"{API}/{created['id']}/action-items/{item_id}/create-task", json={})
    assert task_resp.status_code == 201, task_resp.text
    task = task_resp.json()
    assert task["title"] == "Write the marketing brief"
    assert task["created_by"] == "ai"
    assert task["source_type"] == "meeting_action_item"
    assert task["source_ref"] == created["id"]

    refetched = auth_client.get(f"{API}/{created['id']}")
    assert refetched.json()["action_items"][0]["workgraph_task_id"] == task["id"]

    # Second attempt must be refused -- already linked, not silently re-created.
    again = auth_client.post(f"{API}/{created['id']}/action-items/{item_id}/create-task", json={})
    assert again.status_code == 409


TWO_ITEM_EXTRACTION_JSON = json.dumps(
    {
        "summary": "Two action items were assigned.",
        "decisions": [],
        "action_items": [
            {"description": "Write the marketing brief", "owner": "Bob", "due_date": "next Friday"},
            {"description": "Confirm vendor contract", "owner": "Alice", "due_date": None},
        ],
        "risks": [],
        "unresolved_questions": [],
    }
)


def test_bulk_create_tasks_creates_skips_and_survives_partial_failure(monkeypatch, auth_client):
    """
    Phase 15: (a) already-linked items are skipped, not re-created; (b) a
    failure on one item doesn't roll back or affect another item's already-
    committed task; (c) a repeat call never duplicates the tasks already
    created.
    """
    import app.api.meetings as meetings_module
    from app.schemas.execution import ExecutionResponse, ExecutionStatus

    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", lambda req: _stub_response(TWO_ITEM_EXTRACTION_JSON))
    created = auth_client.post(API, json={"transcript_text": SAMPLE_TRANSCRIPT}).json()
    meeting_id = created["id"]
    item_ids = [i["id"] for i in created["action_items"]]
    assert len(item_ids) == 2

    real_execute = meetings_module.execution_manager.execute

    def flaky_execute(db, request, owner_id):
        if request.task_type == "workgraph.create_task" and request.input["title"] == "Confirm vendor contract":
            return ExecutionResponse(
                execution_id="exec_forced_fail", status=ExecutionStatus.FAILED,
                task_type=request.task_type, error_type="RuntimeError", error_message="forced failure",
            )
        return real_execute(db=db, request=request, owner_id=owner_id)

    monkeypatch.setattr(meetings_module.execution_manager, "execute", flaky_execute)

    resp = auth_client.post(f"{API}/{meeting_id}/action-items/create-tasks", json={})
    assert resp.status_code == 200, resp.text
    results = {r["item_id"]: r for r in resp.json()["results"]}
    assert results[item_ids[0]]["status"] == "created"
    assert results[item_ids[0]]["task_id"] is not None
    assert results[item_ids[1]]["status"] == "failed"
    assert results[item_ids[1]]["task_id"] is None

    # Repeat call: the succeeded item must be skipped (not duplicated), and
    # the still-unlinked failed item gets another real attempt.
    monkeypatch.setattr(meetings_module.execution_manager, "execute", real_execute)
    resp2 = auth_client.post(f"{API}/{meeting_id}/action-items/create-tasks", json={})
    results2 = {r["item_id"]: r for r in resp2.json()["results"]}
    assert results2[item_ids[0]]["status"] == "skipped_already_linked"
    assert results2[item_ids[0]]["task_id"] == results[item_ids[0]]["task_id"]
    assert results2[item_ids[1]]["status"] == "created"

    refetched = auth_client.get(f"{API}/{meeting_id}").json()
    linked = {i["id"]: i["workgraph_task_id"] for i in refetched["action_items"]}
    assert linked[item_ids[0]] == results[item_ids[0]]["task_id"]
    assert linked[item_ids[1]] == results2[item_ids[1]]["task_id"]


def test_meeting_only_visible_to_its_owner(monkeypatch, auth_client, test_user):
    monkeypatch.setattr(meeting_agent_module.runtime_service, "generate", lambda req: _stub_response(SAMPLE_EXTRACTION_JSON))

    created = auth_client.post(API, json={"transcript_text": SAMPLE_TRANSCRIPT}).json()

    db = SessionLocal()
    try:
        other_owner_view = meeting_service.get_meeting(db=db, owner_id="999999", meeting_id=created["id"])
        assert other_owner_view is None

        real_owner_view = meeting_service.get_meeting(db=db, owner_id=str(test_user.id), meeting_id=created["id"])
        assert real_owner_view is not None
    finally:
        db.close()
