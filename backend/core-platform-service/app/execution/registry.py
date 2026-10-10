import logging
from typing import Dict
from app.execution.contracts import (
    CapabilityMetadata,
    ExecutionHandler,
    RAGSearchHandler,
    RAGAnswerHandler,
    DatabaseQueryHandler,
    DatabaseReportHandler,
    TextGenerationHandler,
    DocumentSummaryHandler,
    GmailSendHandler,
    CreateTaskHandler,
    MeetingTranscriptHandler,
    DigestHandler,
    InboxClassifyHandler,
    InboxDraftReplyHandler,
    CommitmentScanHandler,
)

from app.execution.work_handlers import CreateItemHandler, LinkItemsHandler, UpdateItemHandler

logger = logging.getLogger(__name__)


class TaskRegistry:

    def __init__(self):
        self._handlers: Dict[str, ExecutionHandler] = {}
        self._register_default_capabilities()

    def _register_default_capabilities(self):
        self.register("rag_search", RAGSearchHandler())
        self.register("rag_answer", RAGAnswerHandler())
        self.register("database_query", DatabaseQueryHandler())
        self.register("database_report", DatabaseReportHandler())
        self.register("text_generation", TextGenerationHandler())
        self.register("document_summary", DocumentSummaryHandler())
        self.register("gmail.send", GmailSendHandler())
        self.register("workgraph.create_task", CreateTaskHandler())
        self.register("meeting.extract", MeetingTranscriptHandler())
        self.register("digest.daily", DigestHandler())
        self.register("inbox.classify", InboxClassifyHandler())
        self.register("inbox.draft_reply", InboxDraftReplyHandler())
        self.register("commitment.scan", CommitmentScanHandler())
        # AMOF Work: approval-gated AI mutations of WorkGraph (see work_handlers.py)
        self.register("work.create_item", CreateItemHandler())
        self.register("work.update_item", UpdateItemHandler())
        self.register("work.link_items", LinkItemsHandler())

    def register(self, task_type: str, handler: ExecutionHandler):
        clean_task = task_type.lower().strip()
        # A handler with no declared risk/side-effect profile is a bug to
        # catch at registration time -- silently defaulting to "safe" would
        # let a future side-effecting handler (a real Gmail-send capability,
        # say) ship without an approval gate simply by omission.
        if not hasattr(handler, "metadata"):
            raise ValueError(
                f"Handler for task '{clean_task}' ({type(handler).__name__}) "
                "has no CapabilityMetadata -- every ExecutionHandler must "
                "declare one (see app/execution/contracts.py)."
            )
        self._handlers[clean_task] = handler
        logger.info(f"Registered capability handler for task: '{clean_task}'")

    def get_handler(self, task_type: str) -> ExecutionHandler:
        clean_task = task_type.lower().strip()
        if clean_task not in self._handlers:
            raise ValueError(f"Unsupported task_type '{task_type}'. Registered tasks: {list(self._handlers.keys())}")
        return self._handlers[clean_task]

    def get_metadata(self, task_type: str) -> CapabilityMetadata:
        return self.get_handler(task_type).metadata

    def list_supported_tasks(self) -> list[str]:
        return list(self._handlers.keys())

    def list_capabilities(self) -> list[dict]:
        """Structured capability listing -- the actual §9 'agent registry' view."""
        return [
            {"task_type": task, **self._handlers[task].metadata.__dict__}
            for task in sorted(self._handlers)
        ]


task_registry = TaskRegistry()
