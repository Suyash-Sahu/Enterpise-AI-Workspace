from sqlalchemy.orm import Session

from app.services.document_service import DocumentService


class DocumentAgent:

    # =====================================================
    # SUMMARIZE DOCUMENT
    # =====================================================

    def summarize_document(
        self,
        db: Session,
        user_id: int,
        file_id: str,
    ):

        return DocumentService.summarize(
            db=db,
            user_id=user_id,
            file_id=file_id,
        )

    # =====================================================
    # QUESTION ANSWERING
    # =====================================================

    def answer_question(
        self,
        db: Session,
        user_id: int,
        file_id: str,
        question: str,
    ):

        return DocumentService.ask(
            db=db,
            user_id=user_id,
            file_id=file_id,
            question=question,
        )

    # =====================================================
    # BULLET SUMMARY
    # =====================================================

    def bullet_summary(
        self,
        db: Session,
        user_id: int,
        file_id: str,
    ):

        return DocumentService.bullet_summary(
            db=db,
            user_id=user_id,
            file_id=file_id,
        )

    # =====================================================
    # EXTRACT INFORMATION
    # =====================================================

    def extract_information(
        self,
        db: Session,
        user_id: int,
        file_id: str,
        fields: list[str],
    ):

        return DocumentService.extract(
            db=db,
            user_id=user_id,
            file_id=file_id,
            fields=fields,
        )
    # =====================================================
    # COMPARE DOCUMENTS
    # =====================================================

    def compare_documents(
        self,
        db: Session,
        user_id: int,
        first_file_id: str,
        second_file_id: str,
    ):

        return DocumentService.compare(
            db=db,
            user_id=user_id,
            first_file_id=first_file_id,
            second_file_id=second_file_id,
        )


# ---------------------------------------------------------------------------
# Phase 23: Agent-contract wrapper.
#
# PHASE_23.md Task 3 names exactly 8 specialized agents but its Definition
# of Done says "All nine agents registered" and lists document_agent.py
# among the files to modify -- a 9th, unnamed agent. Resolved explicitly
# (see the Phase 23 handoff report and docs/research/PHASE_PROGRESS_11_22.md)
# by adding **DocumentAgent** here (spec.name="DocumentAgent"), role
# "document operations", wrapping the existing DocumentService pipeline
# (summarize/ask/bullet_summary/extract/compare) -- the same reuse
# discipline every other Phase 23 agent follows. Named `DocumentOpsAgent`
# as a Python class (not `DocumentAgent`) purely to avoid shadowing the
# thin `DocumentAgent` class above in this same module, which
# app/api/document.py still imports and instantiates directly -- same
# naming-collision avoidance as InboxTriageAgent/MeetingExtractionAgent.
#
# This agent also backs ExecutionHandler's DocumentSummaryHandler
# (app/execution/contracts.py), which historically does NOT go through
# DocumentService -- it fetches via rag_pipeline._fetch_from_google_connector
# and generates via runtime_service.generate directly (with routing/
# classification metadata DocumentService.summarize does not produce). That
# handler behavior must stay byte-for-byte identical, so it is reproduced
# here verbatim as a second supported input (DocumentSummaryHandlerInput)
# rather than rerouted through DocumentService.summarize, which would
# silently change what the capability actually does.
# ---------------------------------------------------------------------------
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agents.base import Agent, AgentContext, AgentResult, AgentSpec
from app.core.trust_boundary import ContentBlock, ContentSource, render_for_prompt


class DocumentOpsInput(BaseModel):
    """Drives the DocumentService passthrough operations."""
    operation: str  # "summarize" | "ask" | "bullet_summary" | "extract" | "compare"
    file_id: Optional[str] = None
    question: Optional[str] = None
    fields: Optional[list[str]] = None
    first_file_id: Optional[str] = None
    second_file_id: Optional[str] = None


class DocumentSummaryHandlerInput(BaseModel):
    """Reproduces DocumentSummaryHandler's existing file_id/text summarization path."""
    file_id: Optional[str] = None
    text: Optional[str] = None


class DocumentFindings(BaseModel):
    result: Any = None


class DocumentOpsAgent(Agent):
    spec = AgentSpec(
        name="DocumentAgent",
        role="document operations",
        input_schema=DocumentOpsInput,
        output_schema=DocumentFindings,
        tools=["DocumentService"],
        reads_state=["owner_id"],
        writes_state=[],
        side_effect="read_only",
        requires_human_approval=False,
    )

    def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
        if isinstance(inputs, DocumentSummaryHandlerInput):
            return self._run_summary_handler(ctx, inputs)

        assert isinstance(inputs, DocumentOpsInput)
        try:
            user_id = int(ctx.owner_id)
        except (TypeError, ValueError):
            raise ValueError(
                f"owner_id {ctx.owner_id!r} is not a users.id, so document "
                "operations cannot be scoped to a real account's Drive."
            ) from None

        op = inputs.operation
        if op == "summarize":
            result = DocumentService.summarize(db=ctx.db, user_id=user_id, file_id=inputs.file_id)
        elif op == "bullet_summary":
            result = DocumentService.bullet_summary(db=ctx.db, user_id=user_id, file_id=inputs.file_id)
        elif op == "ask":
            result = DocumentService.ask(db=ctx.db, user_id=user_id, file_id=inputs.file_id, question=inputs.question or "")
        elif op == "extract":
            result = DocumentService.extract(db=ctx.db, user_id=user_id, file_id=inputs.file_id, fields=inputs.fields or [])
        elif op == "compare":
            result = DocumentService.compare(
                db=ctx.db, user_id=user_id,
                first_file_id=inputs.first_file_id, second_file_id=inputs.second_file_id,
            )
        else:
            raise ValueError(f"Unsupported DocumentAgent operation: {op!r}")

        return AgentResult(output=DocumentFindings(result=result), evidence=[str(inputs.file_id)] if inputs.file_id else [])

    def _run_summary_handler(self, ctx: AgentContext, inputs: DocumentSummaryHandlerInput) -> AgentResult:
        from app.rag.pipeline import rag_pipeline
        from app.schemas.runtime import RuntimeGenerateRequest
        from app.services.runtime_service import runtime_service

        file_id = inputs.file_id
        text_content = inputs.text

        if file_id and not text_content:
            try:
                user_id = int(ctx.owner_id)
            except (TypeError, ValueError):
                raise ValueError(
                    f"owner_id {ctx.owner_id!r} is not a users.id, so file {file_id!r} "
                    "cannot be fetched from that user's Google Drive without explicit text."
                ) from None
            text_content = rag_pipeline._fetch_from_google_connector(ctx.db, user_id, file_id)

        if not text_content:
            text_content = "No document text content provided for summary."

        # Retrieved document content is untrusted -- same trust-boundary
        # wrapping DocumentSummaryHandler used before this refactor.
        prompt = render_for_prompt([
            ContentBlock(
                content="Please provide a concise summary of the following document.",
                source=ContentSource.SYSTEM,
            ),
            ContentBlock(
                content=text_content[:4000],
                source=ContentSource.RETRIEVED_CONTENT,
                label="document_content",
            ),
        ])

        runtime_req = RuntimeGenerateRequest(
            prompt=prompt,
            execution_mode=ctx.execution_mode,
            timeout=ctx.timeout,
            request_id=ctx.request_id,
            execution_id=ctx.execution_id,
            metadata={
                **(ctx.metadata or {}),
                "classification_content": text_content,
            },
        )

        res = runtime_service.generate(runtime_req)
        return AgentResult(
            output=res,
            evidence=[file_id] if file_id else [],
            model=res.model,
            latency_ms=res.latency_ms,
        )


document_ops_agent = DocumentOpsAgent()