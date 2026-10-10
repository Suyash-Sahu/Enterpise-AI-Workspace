from typing import Optional
from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    file_id: str = Field(..., description="Google Drive file ID or source identifier")
    source: Optional[str] = Field("Enterprise_AI_Workspace_PRD.pdf", description="Document filename or title")
    text: Optional[str] = Field(None, description="Direct text content override")
    chunk_size: Optional[int] = Field(500, description="Character count per chunk")
    chunk_overlap: Optional[int] = Field(100, description="Overlapping characters between adjacent chunks")


class IngestResponse(BaseModel):
    file_id: str
    source: str
    owner_id: str
    chunks_created: int
    total_characters: int
    status: str = "INGESTED"


class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language query string")
    top_k: Optional[int] = Field(5, description="Number of ranked citations to return")
    file_id: Optional[str] = Field(None, description="Optional filter by file ID")
    alpha: Optional[float] = Field(0.5, description="Weighting between vector and keyword search")


class CitationResult(BaseModel):
    chunk_id: str
    file_id: str
    source: str
    owner_id: str
    page: Optional[int] = 1
    chunk_index: int
    text: str
    score: float
    vector_score: float
    keyword_score: float
    rerank_score: float


class SearchResponse(BaseModel):
    query: str
    count: int
    results: list[CitationResult]


class AnswerRequest(BaseModel):
    question: str = Field(..., description="User query or question")
    file_id: Optional[str] = Field(None, description="Optional filter by file ID")
    top_k: Optional[int] = Field(5, description="Citations to retrieve for context")


class AnswerResponse(BaseModel):
    question: str
    answer: str
    citations_count: int
    citations: list[CitationResult]
    # Real generation metadata (Phase 10 token audit, 2026-09-20): None when
    # the answer came from the canned fallback rather than a real completion
    # (ai_service.smart_generate()'s failure path), never a fabricated model
    # name standing in for "we don't know what ran."
    model: Optional[str] = None
    provider: Optional[str] = None
    runtime: Optional[str] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    total_tokens: Optional[int] = None


class IngestedDocumentInfo(BaseModel):
    id: int
    file_id: str
    source: str
    owner_id: str
    chunk_count: int
    ingested_at: str
