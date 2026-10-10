"""
KnowledgeAgent (Phase 23): document grounding.

Tools: rag_pipeline.search/answer -- wraps the existing hybrid-search/
grounded-answer pipeline unchanged. Backs RAGSearchHandler/RAGAnswerHandler
(app/execution/contracts.py), which return rag_pipeline's own result objects
directly, so this agent does the same: `output` is the raw
list[CitationResult] or AnswerResponse rather than a re-derived Evidence[]
copy, keeping the handlers' observable behaviour byte-for-byte identical.
"""
from typing import Optional

from pydantic import BaseModel, Field

from app.agents.base import Agent, AgentContext, AgentResult, AgentSpec
from app.rag.pipeline import rag_pipeline


class KnowledgeSearchInput(BaseModel):
    query: str
    top_k: int = 5
    file_id: Optional[str] = None


class KnowledgeAnswerInput(BaseModel):
    question: str
    top_k: int = 3
    file_id: Optional[str] = None


class Evidence(BaseModel):
    chunk_id: Optional[str] = None
    source: Optional[str] = None
    quote: Optional[str] = None
    score: Optional[float] = None


class KnowledgeAgent(Agent):
    spec = AgentSpec(
        name="KnowledgeAgent",
        role="document grounding",
        input_schema=KnowledgeSearchInput,
        output_schema=Evidence,
        tools=["rag_pipeline"],
        reads_state=["owner_id"],
        writes_state=[],
        side_effect="read_only",
        requires_human_approval=False,
        verifier="EvidenceVerifier",
    )

    def run(self, ctx: AgentContext, inputs: BaseModel) -> AgentResult:
        if isinstance(inputs, KnowledgeAnswerInput):
            res = rag_pipeline.answer(
                db=ctx.db, question=inputs.question, file_id=inputs.file_id,
                owner_id=ctx.owner_id, top_k=inputs.top_k,
            )
            return AgentResult(
                output=res,
                evidence=[c.source for c in res.citations],
                model=res.model,
            )

        assert isinstance(inputs, KnowledgeSearchInput)
        res = rag_pipeline.search(
            db=ctx.db, query=inputs.query, top_k=inputs.top_k,
            file_id=inputs.file_id, owner_id=ctx.owner_id,
        )
        return AgentResult(output=res, evidence=[c.source for c in res])


knowledge_agent = KnowledgeAgent()
