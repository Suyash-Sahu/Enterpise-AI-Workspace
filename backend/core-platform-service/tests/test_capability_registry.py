"""
Regression tests for the capability-metadata extension to the existing
execution registry (app/execution/registry.py, app/execution/contracts.py).

This is NOT a new agent registry -- app/execution/registry.py's TaskRegistry
already dispatches every real capability (rag_search, rag_answer,
database_query, text_generation, document_summary, gmail.send,
workgraph.create_task, meeting.extract) to ExecutionHandler subclasses.
These tests cover the metadata layer added on
top of it: risk level, side-effect classification, and the requirement that
every handler must declare metadata before it can be registered at all.
"""
import pytest

from app.execution.contracts import CapabilityMetadata, ExecutionContext, ExecutionHandler
from app.execution.registry import TaskRegistry, task_registry


def test_all_default_capabilities_declare_metadata():
    for task_type in task_registry.list_supported_tasks():
        meta = task_registry.get_metadata(task_type)
        assert isinstance(meta, CapabilityMetadata)
        assert meta.risk_level in {"low", "medium", "high"}
        assert meta.side_effect in {
            "read_only", "reversible_write", "irreversible_write",
            "external_communication", "destructive",
        }


def test_read_only_capabilities_never_require_approval():
    """
    The five original capabilities are still all read-only and must stay
    that way -- none of them write anywhere external, so none should
    require human approval.
    """
    read_only_tasks = {"rag_search", "rag_answer", "database_query", "text_generation", "document_summary"}
    for task_type in read_only_tasks:
        meta = task_registry.get_metadata(task_type)
        assert meta.side_effect == "read_only"
        assert meta.requires_human_approval is False


def test_gmail_send_is_correctly_classified_as_side_effecting():
    """
    AMOF-X Phase 2/5: gmail.send is the first real side-effecting capability
    in the registry. It must be marked external_communication and
    requires_human_approval=True -- an LLM must never be able to send an
    email without a human approval gate in the way (rule: "the LLM must
    never determine its own permission").
    """
    meta = task_registry.get_metadata("gmail.send")
    assert meta.side_effect == "external_communication"
    assert meta.requires_human_approval is True
    assert meta.risk_level == "high"


def test_list_capabilities_returns_structured_view():
    capabilities = task_registry.list_capabilities()
    task_types = {c["task_type"] for c in capabilities}
    assert task_types == {
        "rag_search", "rag_answer", "database_query", "database_report",
        "text_generation", "document_summary", "gmail.send",
        "workgraph.create_task", "meeting.extract",
        # Phase 16: read-only daily digest composition.
        "digest.daily",
        # Phase 19: inbox triage and reply drafting -- both read-only. The
        # send itself stays gmail.send, so no new guarded capability appears.
        "inbox.classify", "inbox.draft_reply",
        # Pre-existing drift: commitment.scan was registered without updating this set.
        "commitment.scan",
        # AMOF Work: approval-gated AI mutations of WorkGraph (work_handlers.py).
        "work.create_item", "work.update_item", "work.link_items",
    }
    for c in capabilities:
        assert "description" in c and c["description"]
        assert "risk_level" in c
        assert "side_effect" in c


def test_workgraph_create_task_is_reversible_and_unapproved():
    """
    AMOF-X Phase 6: CreateTaskHandler is LOW_SIDE_EFFECT per target spec
    §39's own worked example -- reversible, no approval required, but still
    a real capability going through the normal execution-record path (not a
    read_only capability like the original five, and not requiring approval
    like gmail.send -- a genuinely distinct third point on the risk scale).
    """
    meta = task_registry.get_metadata("workgraph.create_task")
    assert meta.side_effect == "reversible_write"
    assert meta.requires_human_approval is False
    assert meta.risk_level == "low"


def test_meeting_extract_is_read_only_and_unapproved():
    """
    AMOF-X Phase 7: extraction alone never writes anywhere external and
    never dispatches another capability -- it's read_only like the original
    five, not reversible_write like workgraph.create_task, since the only
    write it performs is persisting its own Meeting/MeetingActionItem rows
    (the same "still audited, no approval needed" shape as
    workgraph.create_task, but classified read_only because it does not
    mutate any resource outside its own record of what it extracted).
    """
    meta = task_registry.get_metadata("meeting.extract")
    assert meta.side_effect == "read_only"
    assert meta.requires_human_approval is False
    assert meta.risk_level == "low"


def test_register_rejects_handler_without_metadata():
    """
    A handler that forgets to declare CapabilityMetadata must fail loudly at
    registration, not silently default to "safe" -- that default is exactly
    how a future side-effecting capability could ship without an approval
    gate.
    """

    class NoMetadataHandler(ExecutionHandler):
        def execute(self, db, context: ExecutionContext, input_data: dict) -> dict:
            return {"result": {}}

    registry = TaskRegistry()
    with pytest.raises(ValueError, match="CapabilityMetadata"):
        registry.register("fake_task", NoMetadataHandler())


def test_inbox_capabilities_are_read_only_and_unapproved():
    """
    Phase 19: triage and drafting read and generate text; neither calls a
    Gmail write API, so neither introduces a send path needing its own
    approval gate (the send remains gmail.send). If a future change gives
    either one a side effect, this test fails before the approval-bypass
    sweep has to catch it.
    """
    for task_type in ("inbox.classify", "inbox.draft_reply"):
        meta = task_registry.get_metadata(task_type)
        assert meta.side_effect == "read_only", task_type
        assert meta.requires_human_approval is False, task_type
