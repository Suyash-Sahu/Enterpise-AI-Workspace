import logging
from typing import Any
from sqlalchemy.orm import Session

from app.schemas.execution import ExecutionRequest, ExecutionResponse
from app.supervisor.context import SupervisorContext
from app.services.execution_manager import execution_manager

logger = logging.getLogger(__name__)


class SupervisorExecutionRouter:

    def dispatch(
        self,
        db: Session,
        context: SupervisorContext,
        capability: str,
        resolved_input: dict[str, Any],
        step_id: str,
    ) -> ExecutionResponse:
        """
        Dispatches supervisor step execution directly to P5 Execution Manager.
        Ensures owner_id is propagated strictly from SupervisorContext.
        """
        logger.info(f"[P7 Execution Router]: Dispatching step '{step_id}' ({capability}) for owner '{context.owner_id}'")

        exec_request = ExecutionRequest(
            task_type=capability,
            input=resolved_input,
            execution_mode=context.execution_mode,
            timeout=context.timeout,
            request_id=f"{context.request_id}_{step_id}",
            # Carries the run's cache toggle and the identity the cache key is
            # scoped to. Without a tenant key here, a cache hit could cross
            # tenant boundaries, which would be a worse bug than a cache miss.
            #
            # Scoped on the opaque `owner_id` rather than `context.workspace_id`:
            # that property routes through resolve_user_id(), which raises for
            # any owner_id that is not an integer users.id. Approval filing needs
            # that strictness, but cache scoping does not — the execution layer
            # treats owner_id as an opaque tenant string throughout — and
            # reaching for the property here made every dispatch demand a
            # numeric id it never previously needed.
            metadata={
                **(context.metadata or {}),
                "cache_enabled": context.cache_enabled,
                "workspace_id": f"ws_{context.owner_id}",
                "cache_query": context.question,
            },
        )

        return execution_manager.execute(db=db, request=exec_request, owner_id=context.owner_id)


supervisor_execution_router = SupervisorExecutionRouter()
