import time
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

from app.agents.document_agent import DocumentAgent
from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.document import (
    DocumentSummaryRequest,
    DocumentQuestionRequest,
    DocumentExtractionRequest,
    DocumentCompareRequest,
)
from app.utils.response import success_response, error_response

router = APIRouter(
    prefix="/documents",
    tags=["AI Documents"],
)

agent = DocumentAgent()


@router.post("/summarize")
def summarize_document(
    request: DocumentSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    try:
        summary_text = agent.summarize_document(
            db=db,
            user_id=current_user.id,
            file_id=request.file_id,
        )
        return success_response(
            data={"summary": summary_text, "file_id": request.file_id},
            message="Document summarized successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Request failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/ask")
def ask_document(
    request: DocumentQuestionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    try:
        answer_text = agent.answer_question(
            db=db,
            user_id=current_user.id,
            file_id=request.file_id,
            question=request.question,
        )
        return success_response(
            data={
                "answer": answer_text,
                "question": request.question,
                "file_id": request.file_id,
            },
            message="Document question answered successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Request failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/bullets")
def bullet_summary(
    request: DocumentSummaryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    try:
        bullets = agent.bullet_summary(
            db=db,
            user_id=current_user.id,
            file_id=request.file_id,
        )
        return success_response(
            data={"summary": bullets, "file_id": request.file_id},
            message="Bullet summary generated successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Request failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/extract")
def extract_information(
    request: DocumentExtractionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    try:
        result = agent.extract_information(
            db=db,
            user_id=current_user.id,
            file_id=request.file_id,
            fields=request.fields,
        )
        return success_response(
            data={"result": result, "fields": request.fields, "file_id": request.file_id},
            message="Fields extracted successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Request failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/compare")
def compare_documents(
    request: DocumentCompareRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    start_time = time.time()
    try:
        comp = agent.compare_documents(
            db=db,
            user_id=current_user.id,
            first_file_id=request.first_file_id,
            second_file_id=request.second_file_id,
        )
        return success_response(
            data={
                "comparison": comp,
                "first_file_id": request.first_file_id,
                "second_file_id": request.second_file_id,
            },
            message="Documents compared successfully",
            start_time=start_time,
        )
    except Exception as e:
        return error_response(
            message="Request failed",
            exc=e,
            start_time=start_time,
            status_code=500,
        )


@router.post("/upload", status_code=status.HTTP_501_NOT_IMPLEMENTED)
async def upload_document_vault(
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
):
    """
    Document Vault upload — NOT IMPLEMENTED.

    This previously discarded the uploaded file and returned an invented record
    ("2.4 MB", owner "Alex Dev", indexed: true), so the UI showed a populated
    vault backed by nothing. It now says so instead of claiming success.

    Working alternative: POST /api/v1/rag/ingest, which runs the real chunking
    and vector-indexing pipeline.
    """
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "Document Vault upload is not implemented. "
            "Use POST /api/v1/rag/ingest to index a document."
        ),
    )


@router.get("/{document_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def get_document_details(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Document Vault lookup — NOT IMPLEMENTED. Previously returned fixtures."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Document Vault retrieval is not implemented.",
    )


@router.delete("/{document_id}", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def delete_document_vault(
    document_id: str,
    current_user: User = Depends(get_current_user),
):
    """Document Vault delete — NOT IMPLEMENTED. Previously reported success."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Document Vault deletion is not implemented.",
    )
