"""
M17 — chat runs through the AMOF supervisor, not its own classifier.

Chat used to call SupervisorAgent: a keyword match that picked one agent and
made one call. The real orchestrator existed but nothing users touched went
through it. These tests pin the endpoint to the orchestrator, so a regression
that quietly reintroduces a second supervisor fails here.
"""

from app.models.chat import ChatMessage
from app.models.execution import Execution
from app.supervisor.context import SupervisorContext


def test_chat_answer_carries_a_real_execution_trace(auth_client):
    """
    A chat turn must come back with the plan that produced it: at least one
    execution id from the execution manager, and a steps array.
    """
    response = auth_client.post(
        "/api/v1/chat",
        json={"message": "How many documents do I have indexed?"},
    )

    assert response.status_code == 200
    data = response.json()["data"]

    assert data["agent"] == "AMOFSupervisor"

    # The trace: real ids, minted by the execution manager, not placeholders.
    assert isinstance(data["execution_ids"], list)
    assert len(data["execution_ids"]) >= 1
    assert all(eid for eid in data["execution_ids"])
    assert data["execution_id"] == data["execution_ids"][-1]

    assert isinstance(data["steps"], list)
    assert len(data["steps"]) >= 1
    for step in data["steps"]:
        assert step["step_id"]
        assert step["capability"]
        assert "status" in step

    assert data["status"] in (
        "COMPLETED",
        "FAILED",
        "WAITING_FOR_APPROVAL",
        "CLARIFICATION_REQUIRED",
    )


def test_chat_execution_ids_resolve_to_real_execution_records(
    auth_client, db_session, test_user
):
    """
    The ids are not decorative — each addresses a row the execution manager
    wrote, owned by the caller.

    Asserted against the `executions` table rather than through
    GET /execution-manager/status, because that route hardcodes owner_id="1"
    and cannot see another user's executions. See the M17 report.
    """
    response = auth_client.post(
        "/api/v1/chat",
        json={"message": "How many documents do I have indexed?"},
    )
    assert response.status_code == 200

    execution_ids = response.json()["data"]["execution_ids"]
    assert execution_ids

    for execution_id in execution_ids:
        record = (
            db_session.query(Execution)
            .filter(Execution.id == execution_id)
            .first()
        )
        assert record is not None, (
            f"execution_id {execution_id} reported by chat has no execution row"
        )
        # Filed against the caller, which is what makes the run theirs.
        assert record.owner_id == str(test_user.id)
        assert record.task_type


def test_chat_persists_the_assistant_turn(auth_client, db_session):
    """The turn is stored, and stores the run's last execution id."""
    response = auth_client.post(
        "/api/v1/chat",
        json={"message": "How many documents do I have indexed?"},
    )
    assert response.status_code == 200
    data = response.json()["data"]

    stored = (
        db_session.query(ChatMessage)
        .filter(ChatMessage.public_id == data["id"])
        .first()
    )
    assert stored is not None
    assert stored.role == "assistant"
    assert stored.agent == "AMOFSupervisor"
    assert stored.execution_id == data["execution_id"]
    # Never inferred from an agent name. See the honesty note in app/api/chat.py.
    assert stored.provider is None
    assert stored.runtime is None


def test_chat_history_omits_the_trace_rather_than_inventing_one(auth_client):
    """
    Replayed history has no plan attached — chat_messages cannot store one yet.
    It must leave the fields out, not fabricate an empty step list that reads
    as though the run had no steps.
    """
    post = auth_client.post(
        "/api/v1/chat",
        json={"message": "How many documents do I have indexed?"},
    )
    assert post.status_code == 200
    session_id = post.json()["data"]["session_id"]

    history = auth_client.get(f"/api/v1/chat/session/{session_id}")
    assert history.status_code == 200

    for message in history.json()["data"]["messages"]:
        assert "steps" not in message
        assert "execution_ids" not in message


def test_file_id_reaches_the_plan(auth_client):
    """
    Chat accepts a file_id, and it must survive the hand-off to the planner.
    Before M17 chat passed it straight to a document agent; it now travels as
    $context.file_id, and dropping it would silently narrow what chat can do.
    """
    context = SupervisorContext(
        owner_id="1",
        question="Summarize this",
        file_id="drive-file-abc123",
    )
    assert context.file_id == "drive-file-abc123"

    from app.schemas.supervisor import IntentResult
    from app.supervisor.planner import supervisor_planner

    plan = supervisor_planner.build_plan(
        context=context,
        intent=IntentResult(capability="document_summary", confidence=0.95, reason="test"),
    )
    resolved = supervisor_planner.resolve_step_input(
        step=plan.steps[0], context=context, completed_steps={}
    )
    assert resolved["file_id"] == "drive-file-abc123"
