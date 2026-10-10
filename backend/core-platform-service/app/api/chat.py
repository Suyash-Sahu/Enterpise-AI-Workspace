"""
Chat over the request pipeline.

Two defects are fixed here, both of which made the endpoint look like it worked:

  C11  Sessions lived in a module-level dict keyed only by session id, with no
       user column anywhere. Every signed-in account shared one store, so any
       user could list, read and delete any other user's conversations, and
       everything was lost on restart. Sessions are now rows owned by a user,
       and every query filters on the caller.

  Honesty NFR
       Every answer carried an invented citation — a hardcoded
       "Enterprise_AI_Workspace_PRD.pdf" with a made-up snippet — attached
       whenever a file id was present or the agent name contained "Document".
       The provider was likewise inferred from the agent name and reported as
       fact. Both are gone: citations come from retrieval or the list is
       empty, and provider/runtime are recorded only when actually known.

  M17  Chat used to run its own keyword classifier (SupervisorAgent) that
       picked one agent and made one call, while the real orchestrator sat
       behind /api/v1/supervisor untouched by the product's main surface.
       Two supervisors, and the one users actually reached was the toy. Chat
       now goes through supervisor_service, so every answer here is a real
       plan run through the execution manager.

       A run can end somewhere other than "answered": it can pause for
       approval, ask for clarification, or fail. Those are reported as
       themselves rather than flattened into an assistant message that reads
       like a normal reply.
"""

import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.dependencies import get_current_user, get_db
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.schemas.supervisor import SupervisorRequest, SupervisorResponse
from app.services.supervisor_service import supervisor_service
from app.utils.response import error_response, success_response

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["Workspace Chat"],
)

MAX_TITLE_LENGTH = 200

# A run that paused, asked, or failed is reported as that. Calling all of them
# "processed" is how a half-finished plan starts looking like a success.
_RUN_SUMMARIES = {
    "COMPLETED": "Message processed by the AMOF supervisor",
    "WAITING_FOR_APPROVAL": "Run paused: an action needs your approval",
    "CLARIFICATION_REQUIRED": "Run needs clarification before it can proceed",
    "FAILED": "Run failed before it could answer",
}


def _run_summary(run: SupervisorResponse) -> str:
    return _RUN_SUMMARIES.get(run.status, f"Run ended with status {run.status}")


class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[str] = Field(default=None, max_length=48)
    file_id: Optional[str] = Field(default=None, max_length=256)


class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(default="New Conversation", max_length=MAX_TITLE_LENGTH)


def _owned_session(
    db: Session, user: User, public_id: str
) -> Optional[ChatSession]:
    """
    A session, only if this user owns it.

    Ownership is part of the lookup rather than a check afterwards, so a
    missing row and someone else's row are indistinguishable to the caller —
    both are simply "not found".
    """
    return (
        db.query(ChatSession)
        .filter(
            ChatSession.public_id == public_id,
            ChatSession.user_id == user.id,
        )
        .first()
    )


def _session_summary(session: ChatSession, message_count: int) -> dict[str, Any]:
    return {
        "id": session.public_id,
        "title": session.title,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "updated_at": session.updated_at.isoformat() if session.updated_at else None,
        "message_count": message_count,
    }


def _message_payload(
    message: ChatMessage, run: Optional[SupervisorResponse] = None
) -> dict[str, Any]:
    payload = {
        "id": message.public_id,
        "session_id": message.session.public_id if message.session else None,
        "role": message.role,
        "content": message.content,
        # Kept for the existing frontend, which reads `message` on assistant
        # turns. Same value as `content`.
        "message": message.content,
        "agent": message.agent,
        "provider": message.provider,
        "runtime": message.runtime,
        "execution_id": message.execution_id,
        "sources": message.sources or [],
        "timestamp": message.created_at.isoformat() if message.created_at else None,
    }

    if run is None:
        # Replaying history. The plan is not stored yet — `chat_messages` has
        # one execution_id column and no room for a step graph — so history
        # returns the turn without its trace rather than inventing one.
        # Persisting runs is M18.
        return payload

    payload.update(
        {
            "status": run.status,
            "intent": run.intent.model_dump(),
            "steps": [step.model_dump() for step in run.steps],
            "execution_ids": run.execution_ids,
            "execution_time": run.execution_time,
            "trace_id": run.trace_id,
            "approval_id": run.approval_id,
        }
    )
    return payload


@router.get("/sessions")
def get_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )

    counts = {
        session.id: db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .count()
        for session in sessions
    }

    return success_response(
        data={
            "sessions": [
                _session_summary(session, counts.get(session.id, 0))
                for session in sessions
            ]
        },
        message="Chat sessions retrieved successfully",
        start_time=start_time,
    )


@router.post("/session")
def create_chat_session(
    request: CreateSessionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    session = ChatSession(
        public_id=f"sess_{uuid4().hex[:16]}",
        user_id=current_user.id,
        title=(request.title or "New Conversation")[:MAX_TITLE_LENGTH],
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return success_response(
        data={**_session_summary(session, 0), "messages": []},
        message="Chat session created successfully",
        start_time=start_time,
    )


@router.get("/session/{session_id}")
def get_chat_session_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    session = _owned_session(db, current_user, session_id)

    if session is None:
        # Deliberately identical to a genuinely missing session: the caller
        # learns nothing about other users' session ids.
        return error_response(
            message=f"Session {session_id} not found",
            start_time=start_time,
            status_code=404,
        )

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.id)
        .all()
    )

    return success_response(
        data={
            **_session_summary(session, len(messages)),
            "messages": [_message_payload(m) for m in messages],
        },
        message="Session history retrieved successfully",
        start_time=start_time,
    )


@router.delete("/session/{session_id}")
def delete_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    session = _owned_session(db, current_user, session_id)

    if session is None:
        return error_response(
            message=f"Session {session_id} not found",
            start_time=start_time,
            status_code=404,
        )

    db.delete(session)
    db.commit()

    return success_response(
        data={"deleted": session_id},
        message=f"Session {session_id} deleted successfully",
        start_time=start_time,
    )


@router.post("")
def post_chat_message(
    request: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    session: Optional[ChatSession] = None

    if request.session_id:
        session = _owned_session(db, current_user, request.session_id)

        if session is None:
            return error_response(
                message=f"Session {request.session_id} not found",
                start_time=start_time,
                status_code=404,
            )

    if session is None:
        # First message with no session: open one titled from the question.
        session = ChatSession(
            public_id=f"sess_{uuid4().hex[:16]}",
            user_id=current_user.id,
            title=request.message[:60] or "New Conversation",
        )
        db.add(session)
        db.flush()

    db.add(
        ChatMessage(
            public_id=f"msg_{uuid4().hex[:16]}",
            session_id=session.id,
            user_id=current_user.id,
            role="user",
            content=request.message,
            sources=[],
        )
    )

    try:
        run = supervisor_service.execute(
            db=db,
            request=SupervisorRequest(
                question=request.message,
                execution_mode="auto",
                conversation_id=session.public_id,
                metadata={"file_id": request.file_id} if request.file_id else {},
            ),
            owner_id=str(current_user.id),
        )
    except Exception as exc:
        db.commit()  # keep the user's turn; the failure is the assistant's
        return error_response(
            message="The request pipeline could not answer this message",
            exc=exc,
            start_time=start_time,
            status_code=500,
        )

    answer = ChatMessage(
        public_id=f"msg_{uuid4().hex[:16]}",
        session_id=session.id,
        user_id=current_user.id,
        role="assistant",
        content=run.answer,
        # The run is the supervisor's, not any single agent's — a plan may span
        # several capabilities. Which ones is in `steps`; naming one here would
        # be a guess as soon as plans stop being one step long.
        agent="AMOFSupervisor",
        # Left unset deliberately. SupervisorResponse reports these per step,
        # not per run, and the honesty rule above forbids inferring them.
        provider=None,
        runtime=None,
        # One column, so the last execution stands for the run; the full list
        # rides in the response payload.
        execution_id=run.execution_ids[-1] if run.execution_ids else None,
        # Citations only if retrieval actually produced them.
        sources=run.sources or [],
    )

    db.add(answer)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(answer)

    return success_response(
        data=_message_payload(answer, run=run),
        message=_run_summary(run),
        start_time=start_time,
    )


@router.post("/stream")
def post_chat_message_stream(
    request: SendMessageRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Placeholder for token streaming.

    KNOWN LIMITATION: this does not stream. It returns the same single
    response as POST /chat, and is kept only so the route does not 404 for
    clients that already call it.
    """
    return post_chat_message(request, db, current_user)
