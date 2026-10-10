import time
import uuid
import json
import logging
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.execution import Execution
from app.schemas.execution import ExecutionRequest, ExecutionResponse, ExecutionStatus
from app.execution.contracts import ExecutionContext
from app.execution.registry import task_registry
from app.execution.policies import execution_policy
from app.execution.retry import retry_manager
from app.execution.metrics import execution_metrics
from app.cache.service import cache_service
from app.runtime.exceptions import RateLimitedError
from app.services.approval.approval_policy import approval_policy
from app.services.approval.approval_service import approval_service
from app.services.audit_service import log_execution

logger = logging.getLogger(__name__)


def _is_side_effecting(task_type: str) -> bool:
    """
    AMOF-X Phase 20: the capability's own declared metadata decides, exactly
    as it does for the approval gate -- not a second hand-maintained list
    that would drift from it. An unregistered task_type never reached a
    handler, so nothing happened that needs auditing.
    """
    try:
        return task_registry.get_metadata(task_type).side_effect != "read_only"
    except Exception:
        return False


class ExecutionExecutor:

    @staticmethod
    def execute_task(
        db: Session,
        request: ExecutionRequest,
        owner_id: str,
    ) -> ExecutionResponse:
        """
        Executes an AI task through the P5 execution state machine:
        CREATED -> VALIDATING -> RUNNING -> COMPLETED (or FAILED/TIMEOUT).
        Handles idempotency lookups, parameter validation, handler dispatch, retries, and secret masking.
        """
        start_time = time.time()
        request_id = request.request_id or f"req_{uuid.uuid4().hex[:10]}"
        idempotency_key = request.idempotency_key
        # Set inside the try block only when an approval claim actually
        # succeeds -- initialized here so the except handler below can
        # safely check them even if the claim itself (or an earlier step)
        # is what failed.
        approval_claimed = False
        approval_owner_id = None
        # Phase 20: exactly one audit row per side-effecting execution --
        # written on whichever path the execution actually ends on.
        audited = False

        # 1. Idempotency Check: if idempotency_key provided and already completed, return existing result
        if idempotency_key:
            existing = db.query(Execution).filter(
                Execution.owner_id == str(owner_id),
                Execution.idempotency_key == idempotency_key,
                Execution.status == ExecutionStatus.COMPLETED.value,
            ).first()

            if existing:
                logger.info(f"[Idempotency Hit]: Returning existing execution '{existing.id}' for key '{idempotency_key}'")
                result_data = json.loads(existing.result_json) if existing.result_json else {}
                return ExecutionResponse(
                    execution_id=existing.id,
                    status=ExecutionStatus(existing.status),
                    task_type=existing.task_type,
                    result=result_data,
                    provider=existing.provider,
                    model=existing.model,
                    execution_time=existing.execution_time,
                    retry_count=existing.retry_count,
                    idempotency_key=existing.idempotency_key,
                    request_id=existing.request_id,
                )

        # 2. State: CREATED
        exec_record = Execution(
            owner_id=str(owner_id),
            request_id=request_id,
            idempotency_key=idempotency_key,
            task_type=request.task_type.lower().strip(),
            execution_mode=request.execution_mode or "auto",
            status=ExecutionStatus.CREATED.value,
            input_json=execution_metrics.to_json_str(request.input),
            retry_count=0,
            created_at=datetime.now(timezone.utc),
        )
        db.add(exec_record)
        db.commit()
        db.refresh(exec_record)

        try:
            # 3. State: VALIDATING
            exec_record.status = ExecutionStatus.VALIDATING.value
            db.commit()

            clean_mode = execution_policy.validate_mode(request.execution_mode)
            timeout = execution_policy.resolve_timeout(request.timeout)
            handler = task_registry.get_handler(request.task_type)

            # --- Cache lookup ---
            #
            # `cache_enabled` in request metadata is the per-run ablation
            # toggle; cache_policy additionally enforces the global
            # settings.CACHE_ENABLED and the side-effect bypass, so a
            # side-effecting capability can never be served from cache no
            # matter what this flag says.
            req_meta = request.metadata or {}
            cache_on = bool(req_meta.get("cache_enabled", True))
            cache_query = req_meta.get("cache_query") or execution_metrics.to_json_str(
                request.input
            )
            workspace_id = req_meta.get("workspace_id") or f"ws_user_{owner_id}"

            if cache_on:
                cached = cache_service.get(
                    query=cache_query,
                    capability=request.task_type,
                    user_id=str(owner_id),
                    workspace_id=str(workspace_id),
                    action_type=request.task_type,
                )
                if cached is not None:
                    execution_time = round(time.time() - start_time, 3)
                    logger.info(
                        "[Execution Cache HIT]: task=%s execution=%s",
                        request.task_type,
                        exec_record.id,
                    )
                    payload = dict(cached) if isinstance(cached, dict) else {"result": cached}
                    payload["cache_hit"] = True

                    exec_record.status = ExecutionStatus.COMPLETED.value
                    exec_record.result_json = execution_metrics.to_json_str(payload)
                    exec_record.provider = "cache"
                    exec_record.model = "cache"
                    exec_record.execution_time = execution_time
                    exec_record.completed_at = datetime.now(timezone.utc)
                    db.commit()

                    return ExecutionResponse(
                        execution_id=exec_record.id,
                        status=ExecutionStatus.COMPLETED,
                        task_type=exec_record.task_type,
                        result=payload,
                        provider="cache",
                        model="cache",
                        execution_time=execution_time,
                        retry_count=0,
                        idempotency_key=idempotency_key,
                        request_id=request_id,
                    )

            context = ExecutionContext(
                owner_id=str(owner_id),
                execution_id=exec_record.id,
                request_id=request_id,
                idempotency_key=idempotency_key,
                timeout=timeout,
                execution_mode=clean_mode,
                metadata=request.metadata or {},
            )

            # --- Approval claim gate (defense in depth, AMOF-X Phase 5) ---
            #
            # This is the structural backstop, not the primary gate: normal
            # traffic through app/supervisor/supervisor.py never reaches here
            # for an approval-required capability -- it creates the Approval
            # and returns WAITING_FOR_APPROVAL instead of dispatching. This
            # exists so that *no* caller -- today's supervisor, a future
            # automation worker, or a direct script -- can reach
            # handler.execute() for a side-effecting capability without a
            # real, approved Approval row that this call atomically consumes
            # (begin_execution's APPROVED -> EXECUTING update is a real DB
            # claim, not a status read). "The LLM must never determine its
            # own permission" only holds if the enforcement point can't be
            # routed around.
            #
            # The claimed effective_payload (the approved, possibly-edited
            # payload) replaces request.input for dispatch -- not what the
            # caller passed at execute-time -- the same invariant
            # app/api/connectors.py's gmail/send endpoint already enforces
            # for its own hand-built path, generalized here to any
            # registered side-effecting capability.
            effective_input = request.input
            if approval_policy.requires_approval(request.task_type):
                if not request.approval_id:
                    raise PermissionError(
                        f"'{request.task_type}' requires a valid, approved Approval "
                        "record; none was supplied (ExecutionRequest.approval_id)."
                    )
                try:
                    approval_owner_id = int(owner_id)
                except (TypeError, ValueError):
                    raise ValueError(
                        f"owner_id {owner_id!r} is not a users.id, so this run cannot "
                        "claim an approval: Approval.user_id is a real int FK."
                    ) from None

                effective_input = approval_service.begin_execution(
                    db=db,
                    approval_id=request.approval_id,
                    user_id=approval_owner_id,
                    workspace_id=str(workspace_id),
                    expected_action_type=request.task_type,
                )
                approval_claimed = True

            # 4. State: RUNNING
            exec_record.status = ExecutionStatus.RUNNING.value
            exec_record.started_at = datetime.now(timezone.utc)
            db.commit()

            # 5. Execute handler with bounded retries
            handler_result, retries_used = retry_manager.execute_with_retry(
                func=lambda: handler.execute(db=db, context=context, input_data=effective_input)
            )

            execution_time = round(time.time() - start_time, 3)

            # 6. State: COMPLETED
            result_payload = handler_result.get("result", {})
            provider_meta = handler_result.get("provider", "ai_platform")
            model_meta = handler_result.get("model", "default")

            # Carry the handler's token usage into the persisted payload.
            #
            # TextGenerationHandler and DocumentSummaryHandler compute real
            # token counts from the runtime response and return them as a
            # sibling "tokens" key on handler_result -- but only "result" was
            # ever pulled out to build result_payload, so that real data was
            # computed and then discarded on every single call. Every
            # downstream reader of Execution.result_json (the evaluation
            # harness) then found no "tokens" key and silently substituted a
            # hardcoded 120/80 -- a fabricated constant standing in for a
            # measurement that had already been made and thrown away.
            tokens_meta = handler_result.get("tokens")
            if tokens_meta and isinstance(result_payload, dict):
                result_payload = {**result_payload, "tokens": tokens_meta}

            routing_meta = handler_result.get("routing")
            if routing_meta and isinstance(result_payload, dict):
                result_payload = {**result_payload, "routing": routing_meta}

            exec_record.status = ExecutionStatus.COMPLETED.value
            exec_record.result_json = execution_metrics.to_json_str(result_payload)
            exec_record.provider = provider_meta
            exec_record.model = model_meta
            # Record where this actually ran, not what was requested. The
            # record previously kept the literal "auto", so nothing downstream
            # could tell local from cloud and any placement measurement built
            # on this column was meaningless.
            exec_record.execution_mode = handler_result.get("runtime") or clean_mode
            exec_record.retry_count = retries_used
            exec_record.execution_time = execution_time
            exec_record.completed_at = datetime.now(timezone.utc)
            db.commit()

            if approval_claimed:
                approval_service.complete_execution(
                    db=db, approval_id=request.approval_id, user_id=approval_owner_id,
                )

            # --- Cache store ---
            # Only successful results are cached, and cache_policy again
            # refuses side-effecting capabilities here, so the write path
            # cannot poison the read path with an un-cacheable action.
            if cache_on:
                cache_service.set(
                    query=cache_query,
                    value=result_payload,
                    capability=request.task_type,
                    user_id=str(owner_id),
                    workspace_id=str(workspace_id),
                    action_type=request.task_type,
                    model=model_meta,
                )

            if _is_side_effecting(exec_record.task_type):
                log_execution(
                    db=db, owner_id=str(owner_id), execution_id=exec_record.id,
                    task_type=exec_record.task_type, status="COMPLETED",
                )
                audited = True

            return ExecutionResponse(
                execution_id=exec_record.id,
                status=ExecutionStatus.COMPLETED,
                task_type=exec_record.task_type,
                result=result_payload,
                provider=provider_meta,
                model=model_meta,
                execution_time=execution_time,
                retry_count=retries_used,
                idempotency_key=idempotency_key,
                request_id=request_id,
            )

        except Exception as e:
            execution_time = round(time.time() - start_time, 3)
            error_msg = str(e)
            logger.error(f"[Execution Engine Failed]: id={exec_record.id} error={error_msg}")

            exec_record.status = ExecutionStatus.FAILED.value
            exec_record.error_type = type(e).__name__
            exec_record.error_message = error_msg
            exec_record.execution_time = execution_time
            exec_record.completed_at = datetime.now(timezone.utc)
            # RateLimitedError is raised only by the cloud runtime's own HTTP
            # dispatch (an HTTP 429 from a cloud provider -- see its
            # docstring), so its mere occurrence is unambiguous proof this
            # was a cloud attempt, even though it failed before the success
            # path (line ~246 above) ever ran to record the real placement.
            # Without this, exec_record.execution_mode keeps its creation-time
            # value (often "auto", set from an unresolved routing request),
            # so evaluation-level actual_execution_mode aggregation
            # (app/evaluation/executor.py's `rec.execution_mode == "cloud"`
            # check) silently undercounts genuinely-attempted-but-rate-
            # limited cloud placements as unknown/local.
            if isinstance(e, RateLimitedError):
                exec_record.execution_mode = "cloud"
            db.commit()

            # Only reached if the claim itself succeeded and the handler
            # (or something after it) then failed -- a claim that never
            # succeeded (missing/invalid approval_id) leaves the Approval
            # untouched, which is correct: nothing was consumed.
            if approval_claimed:
                try:
                    approval_service.fail_execution(
                        db=db, approval_id=request.approval_id,
                        user_id=approval_owner_id, error_message=error_msg,
                    )
                except Exception:
                    logger.exception("Failed to record approval execution failure")

            # A failed side-effecting execution is exactly the event an audit
            # trail exists for: the attempt is recorded, with its outcome,
            # never omitted because it did not succeed.
            if not audited and _is_side_effecting(exec_record.task_type):
                log_execution(
                    db=db, owner_id=str(owner_id), execution_id=exec_record.id,
                    task_type=exec_record.task_type, status="FAILED",
                )
                audited = True

            return ExecutionResponse(
                execution_id=exec_record.id,
                status=ExecutionStatus.FAILED,
                task_type=exec_record.task_type,
                result=None,
                execution_time=execution_time,
                retry_count=exec_record.retry_count,
                idempotency_key=idempotency_key,
                request_id=request_id,
                error_type=type(e).__name__,
                error_message=error_msg,
            )


execution_executor = ExecutionExecutor()
