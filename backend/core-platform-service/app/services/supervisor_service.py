import logging
from sqlalchemy.orm import Session

from app.schemas.supervisor import (
    SupervisorRequest,
    SupervisorResponse,
    SupervisorHealthResponse,
    SupervisorPlan,
    IntentResult,
)
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor
from app.supervisor.intent import intent_analyzer
from app.supervisor.planner import supervisor_planner
from app.core.config import settings

logger = logging.getLogger(__name__)


class SupervisorService:

    @staticmethod
    def execute(db: Session, request: SupervisorRequest, owner_id: str) -> SupervisorResponse:
        """
        Executes P7 supervisor orchestration pipeline for authenticated owner_id.
        """
        context = SupervisorContext(
            owner_id=owner_id,
            question=request.question,
            execution_mode=request.execution_mode or "auto",
            timeout=request.timeout or settings.SUPERVISOR_DEFAULT_TIMEOUT,
            conversation_id=request.conversation_id,
            file_id=(request.metadata or {}).get("file_id"),
            metadata=request.metadata or {},
        )

        return amof_supervisor.run(db=db, context=context)

    @staticmethod
    def classify(db: Session, request: SupervisorRequest, owner_id: str) -> IntentResult:
        """
        Returns intent classification result for user query.
        """
        context = SupervisorContext(
            owner_id=owner_id,
            question=request.question,
            execution_mode=request.execution_mode or "auto",
        )
        intent, _ = intent_analyzer.analyze(db=db, context=context)
        return intent

    @staticmethod
    def plan(db: Session, request: SupervisorRequest, owner_id: str) -> SupervisorPlan:
        """
        Generates and returns DAG execution plan for user query.
        """
        context = SupervisorContext(
            owner_id=owner_id,
            question=request.question,
            execution_mode=request.execution_mode or "auto",
        )
        intent, _ = intent_analyzer.analyze(db=db, context=context)
        return supervisor_planner.build_plan(context=context, intent=intent)

    @staticmethod
    def health() -> SupervisorHealthResponse:
        """
        Returns supervisor operational health telemetry without making LLM calls.
        """
        return SupervisorHealthResponse(
            status="online" if settings.SUPERVISOR_ENABLED else "disabled",
            supervisor_enabled=settings.SUPERVISOR_ENABLED,
            p5_available=settings.EXECUTION_MANAGER_ENABLED,
            supported_capabilities=[
                "rag_search",
                "rag_answer",
                "database_query",
                "text_generation",
                "document_summary",
            ],
            max_steps=settings.SUPERVISOR_MAX_STEPS,
            max_timeout_seconds=settings.SUPERVISOR_MAX_TIMEOUT,
        )


supervisor_service = SupervisorService()
