import time
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.rag import IngestRequest, SearchRequest, AnswerRequest
from app.rag.pipeline import rag_pipeline
from app.utils.response import success_response, error_response

router = APIRouter(
    prefix="/rag",
    tags=["Project 3 — Retrieval Service (RAG)"],
)


@router.post("/ingest")
def ingest_document(
    request: IngestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    try:
        res = rag_pipeline.ingest(
            db=db,
            file_id=request.file_id,
            source=request.source or "Enterprise_AI_Workspace_PRD.pdf",
            owner_id=str(current_user.id),
            text=request.text,
            chunk_size=request.chunk_size or 500,
            chunk_overlap=request.chunk_overlap or 100,
        )
        return success_response(
            data=res.model_dump(),
            message="Document text ingested and vector indexed successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Ingestion failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/search")
def search_rag(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    try:
        results = rag_pipeline.search(
            db=db,
            query=request.query,
            top_k=request.top_k or 5,
            file_id=request.file_id,
            owner_id=str(current_user.id),
            alpha=request.alpha if request.alpha is not None else 0.5,
        )
        res_dicts = [r.model_dump() for r in results]
        return success_response(
            data={
                "query": request.query,
                "count": len(res_dicts),
                "results": res_dicts,
            },
            message=f"Retrieved {len(res_dicts)} ranked citations",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Search failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/answer")
def answer_rag(
    request: AnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    try:
        ans = rag_pipeline.answer(
            db=db,
            question=request.question,
            top_k=request.top_k or 5,
            file_id=request.file_id,
            owner_id=str(current_user.id),
        )
        return success_response(
            data=ans.model_dump(),
            message="Grounded RAG answer generated successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Grounded answer generation failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.get("/documents")
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    docs = rag_pipeline.list_documents(db=db, owner_id=str(current_user.id))
    doc_dicts = [d.model_dump() for d in docs]
    return success_response(
        data={"count": len(doc_dicts), "documents": doc_dicts},
        message="Ingested documents retrieved successfully",
        start_time=start_time,
    )


@router.delete("/document/{file_id}")
def delete_document(
    file_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    deleted = rag_pipeline.delete_document(db=db, file_id=file_id, owner_id=str(current_user.id))
    return success_response(
        data={"file_id": file_id, "deleted": deleted},
        message=f"Document chunks and vectors for file ID '{file_id}' deleted",
        start_time=start_time,
    )
