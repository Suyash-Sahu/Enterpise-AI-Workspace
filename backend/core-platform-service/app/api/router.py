from fastapi import APIRouter, Depends

from app.api.admin import router as admin_router
from app.api.approvals import router as approvals_router
from app.api.automations import router as automations_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.calendar import router as calendar_router
from app.cache.health import router as cache_health_router
from app.api.chat import router as chat_router
from app.api.commitments import router as commitments_router
from app.api.connectors import public_router as connectors_public_router
from app.api.connectors import router as connectors_router
from app.api.db_agent import router as db_agent_router
from app.api.document import router as document_router
from app.api.evaluation import router as evaluation_router
from app.api.execution_manager import router as execution_manager_router
from app.api.health import router as health_router
from app.api.meetings import router as meetings_router
from app.api.notifications import router as notifications_router
from app.api.rag import router as rag_router
from app.api.runtime import router as runtime_router
from app.api.supervisor import router as supervisor_router
from app.api.traces import router as traces_router
from app.api.users import router as users_router
from app.api.workgraph import router as workgraph_router
from app.api.workgraph_ai import router as workgraph_ai_router
from app.api.workgraph_automations import router as workgraph_automations_router
from app.api.workspace import router as workspace_router
from app.api.writer import router as writer_router
from app.core.dependencies import get_current_user

# Central Master Router mounted at /api/v1
api_router = APIRouter(prefix="/api/v1")

# Authentication is applied here, at mount time, rather than route by route.
# A router added to the protected block below is authenticated by default, so
# a new endpoint cannot be left open by forgetting a decorator.
PROTECTED = [Depends(get_current_user)]

# --- Public: unauthenticated by design -------------------------------------
# health          — liveness probe, no data
# auth            — issues credentials; cannot require them
# connectors_public — Google's OAuth redirect target (identity comes from the
#                     signed, user-bound, single-use state row)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(connectors_public_router)
# Operational telemetry only — hit counts, namespace, schema version.
# No credentials. Defined in app/cache/health.py but never mounted.
api_router.include_router(cache_health_router)

# --- Protected -------------------------------------------------------------
api_router.include_router(users_router)
api_router.include_router(connectors_router)
api_router.include_router(workspace_router, dependencies=PROTECTED)
api_router.include_router(document_router, dependencies=PROTECTED)
api_router.include_router(rag_router, dependencies=PROTECTED)
api_router.include_router(chat_router, dependencies=PROTECTED)
api_router.include_router(writer_router, dependencies=PROTECTED)
api_router.include_router(notifications_router, dependencies=PROTECTED)
api_router.include_router(traces_router, dependencies=PROTECTED)
# These two already declare per-route auth (and expose a public /health).
api_router.include_router(approvals_router)
api_router.include_router(evaluation_router)

# admin_router enforces the 'admin' role via require_role; audit_router
# requires a signed-in user. Both were defined but never mounted, which left
# audit logging unreachable entirely (finding M11).
api_router.include_router(audit_router, dependencies=PROTECTED)
api_router.include_router(admin_router)

api_router.include_router(
    db_agent_router,
    prefix="/db-agent",
    tags=["Database Agent"],
    dependencies=PROTECTED,
)
api_router.include_router(
    execution_manager_router,
    prefix="/execution-manager",
    tags=["Execution Manager"],
    dependencies=PROTECTED,
)
api_router.include_router(
    runtime_router,
    prefix="/runtime",
    tags=["Model Runtime Gateway"],
    dependencies=PROTECTED,
)
api_router.include_router(
    supervisor_router,
    prefix="/supervisor",
    tags=["AMOF Supervisor"],
    dependencies=PROTECTED,
)
api_router.include_router(workgraph_router, dependencies=PROTECTED)
api_router.include_router(workgraph_ai_router, dependencies=PROTECTED)
api_router.include_router(workgraph_automations_router, dependencies=PROTECTED)
api_router.include_router(meetings_router, dependencies=PROTECTED)
api_router.include_router(automations_router, dependencies=PROTECTED)
api_router.include_router(calendar_router, dependencies=PROTECTED)
api_router.include_router(commitments_router, dependencies=PROTECTED)
