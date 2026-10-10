import json
import time
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.evaluation.schemas import DatasetItemSchema, EvaluationConfigSchema, EvaluationResultItemSchema
from app.evaluation.quality_judge import quality_judge
from app.privacy.classifier import privacy_classifier
from app.supervisor.context import SupervisorContext
from app.supervisor.supervisor import amof_supervisor
from app.models.execution import Execution

from app.utils.timeutils import utcnow_naive

logger = logging.getLogger(__name__)


class TaskExecutor:
    """
    Executes benchmark tasks through the actual P7 AMOF Supervisor pipeline and captures empirical execution traces.
    """

    @classmethod
    def execute_task(
        cls,
        db: Session,
        task: DatasetItemSchema,
        config: EvaluationConfigSchema,
        override_mode: Optional[str] = None,
    ) -> EvaluationResultItemSchema:
        start_dt = utcnow_naive()
        t0 = time.time()

        mode = override_mode if override_mode is not None else config.execution_mode

        # Baseline C logic: Static Rule (simple -> local, complex/medium -> cloud)
        if mode == "static_rule":
            mode = "local" if task.complexity == "simple" else "cloud"
        elif mode == "always_local":
            # Unlike "always_cloud" (below), this needs no override: "local" is
            # unconditionally permitted by the privacy constraint, so there is
            # no refusal path to route around. Passing the literal string
            # "always_local" straight through, unmapped, was a real bug this
            # harness's baseline sweep caught the first time anything actually
            # ran the ALWAYS_LOCAL baseline end-to-end: RuntimePolicy only
            # accepts {auto, local, cloud} and rejected every single task.
            mode = "local"

        # The ALWAYS_CLOUD baseline has to be able to place sensitive tasks in
        # the cloud, otherwise it is not an unconstrained baseline and the
        # privacy comparison has nothing to compare against. This is the only
        # legitimate use of the override; RuntimePolicy logs it at WARNING.
        metadata: dict = {
            "eval_task_id": task.task_id,
            "eval_category": task.category,
        }
        if override_mode == "always_cloud":
            metadata["privacy_max_cloud_label"] = "confidential"

        context = SupervisorContext(
            owner_id="1",
            question=task.task,
            execution_mode="auto" if override_mode == "always_cloud" else mode,
            # Typed toggles, consulted on real branches. Previously these went
            # into metadata as strings and were read by nothing, which made
            # every ablation arm produce identical numbers.
            cache_enabled=config.cache_enabled,
            verification_enabled=config.verification_enabled,
            hitl_enabled=config.hitl_enabled,
            metadata=metadata,
        )

        error_type = None
        error_message = None
        response = None

        try:
            response = amof_supervisor.run(db=db, context=context)
        except Exception as e:
            logger.error(f"[Evaluation TaskExecutor] Execution failed for task {task.task_id}: {str(e)}")
            error_type = type(e).__name__
            error_message = str(e)

        t1 = time.time()
        end_dt = utcnow_naive()
        latency_ms = round((t1 - t0) * 1000.0, 2)

        # Process supervisor response telemetry
        status_str = response.status if response else "FAILED"
        completion_success = status_str in {"COMPLETED", "WAITING_FOR_APPROVAL"}

        # actual_capability must be None on failure, never task.expected_capability.
        # It previously fell back to the ground-truth label whenever the run
        # produced no intent (an exception before intent classification, or a
        # crashed supervisor) -- the exact leak class from privacy_classification
        # at executor.py:166 (fixed in Week 1), just recurring on a different
        # field. No metric currently reads actual_capability against
        # expected_capability, but both are exported side by side in every CSV
        # and API payload, and "intent classification accuracy" is the obvious
        # next metric someone adds from that data. Silently backfilling the
        # correct answer on failure would make that metric look inflated on
        # exactly the runs that should count against it.
        actual_capability = response.intent.capability if (response and response.intent) else None

        # actual_mode/actual_model/cloud_execution start as None ("unknown"),
        # not "local". They previously defaulted to "local" unconditionally,
        # so a task where amof_supervisor.run() raised before ever dispatching
        # a step (no Execution record exists at all -- e.g. an intent-
        # classification-level crash) was silently reported as a successful
        # local execution, indistinguishable from one that genuinely ran
        # local. Confirmed via direct test: mocking amof_supervisor.run to
        # raise produced actual_execution_mode="local", cloud_execution=False
        # with no execution ever attempted (Phase 10 audit). "Unknown" is
        # only resolved to a concrete value once we find real evidence below
        # of what was actually dispatched.
        actual_mode: Optional[str] = None
        actual_model: Optional[str] = None
        cloud_execution: Optional[bool] = None

        # Inspect execution records from P5.
        #
        # This previously defaulted every step to 120/80 tokens whenever the
        # step's result_json had no "tokens" key -- which was EVERY step,
        # because the persistence layer discarded the handler's real token
        # counts before they ever reached result_json (fixed separately in
        # execution/executor.py), and because the key names here
        # ("prompt_tokens"/"completion_tokens") never matched what the handler
        # actually produces ("input"/"output"). Every token and cost number
        # this evaluator has ever reported was therefore a fabricated
        # constant, not a measurement, regardless of what the run actually did.
        #
        # Now: a step contributes real numbers only when result_json actually
        # carries them. If NO step in the run reports usage, input/output/total
        # tokens stay None -- "not measured", which MetricsEngine already
        # reports as METRIC_UNAVAILABLE -- rather than a plausible-looking
        # fake number silently standing in for a missing measurement.
        input_tokens: Optional[int] = None
        output_tokens: Optional[int] = None
        total_tokens: Optional[int] = None
        estimated_cost: Optional[float] = None
        cache_hit = False
        tokens_measured = False

        exec_records = []
        if response and response.execution_ids:
            exec_records = db.query(Execution).filter(Execution.id.in_(response.execution_ids)).all()

        if exec_records:
            # At least one capability was actually dispatched (the Execution
            # row's execution_mode is set at dispatch time, independent of
            # whether that dispatch later succeeded or failed -- confirmed by
            # direct test: a real Execution row with execution_mode="cloud"
            # and status="FAILED" correctly yields actual_execution_mode=
            # "cloud", cloud_execution=True, completion_success=False here.
            # So "local" is now a resolved fact ("this ran, and nothing
            # marked it cloud"), not a fallback guess.
            actual_mode = "local"
            actual_model = config.local_model
            cloud_execution = False

        for rec in exec_records:
            # rec.model is the model the runtime layer actually dispatched to
            # (e.g. "qwen2.5:3b-instruct"); config.local_model/cloud_model are
            # fixed schema defaults ("ollama/qwen2.5-coder") never updated to
            # match a real run. Reproducibility requires recording what ran,
            # not a placeholder -- fall back to the config default only when
            # the Execution row itself has no model recorded.
            if rec.model:
                actual_model = rec.model
            if rec.execution_mode == "cloud" or rec.provider == "openrouter":
                actual_mode = "cloud"
                if not rec.model:
                    actual_model = config.cloud_model
                cloud_execution = True

            # Check for token usage and cache_hit safely
            result_data = None
            if rec.result_json:
                if isinstance(rec.result_json, str):
                    try:
                        result_data = json.loads(rec.result_json)
                    except Exception:
                        result_data = None
                elif isinstance(rec.result_json, dict):
                    result_data = rec.result_json

            if isinstance(result_data, dict) and isinstance(result_data.get("tokens"), dict):
                tokens_info = result_data["tokens"]
                step_input = tokens_info.get("input")
                step_output = tokens_info.get("output")
                if step_input is not None and step_output is not None:
                    input_tokens = (input_tokens or 0) + int(step_input)
                    output_tokens = (output_tokens or 0) + int(step_output)
                    tokens_measured = True

            if isinstance(result_data, dict) and result_data.get("cache_hit"):
                cache_hit = True

        if tokens_measured:
            total_tokens = input_tokens + output_tokens

        # If override_mode was set to always_cloud / always_local
        if override_mode == "always_cloud":
            actual_mode = "cloud"
            actual_model = config.cloud_model
            cloud_execution = True
        elif override_mode == "always_local":
            actual_mode = "local"
            actual_model = config.local_model
            cloud_execution = False

        if cloud_execution and total_tokens is not None:
            # $0.003 / 1k tokens is a declared PRICING ASSUMPTION (roughly
            # GPT-4o-mini-class blended rate), not a measurement -- unlike the
            # token counts themselves, which must come from what actually ran.
            # Left unset (None) rather than computed from a fabricated total
            # when no step reported real usage.
            estimated_cost = round((total_tokens / 1000.0) * 0.003, 6)

        # Routing accuracy check -- LOCAL/CLOUD PLACEMENT ONLY. This must never
        # be conflated with capability correctness below: a smoke evaluation
        # (2026-09-20) found a rag_answer task that the intent classifier
        # misrouted to database_query still landed "local" (matching
        # expected_execution_mode), so routing_correct=True hid a completely
        # wrong capability choice.
        routing_correct = (actual_mode == task.expected_execution_mode)

        # Capability classification accuracy -- kept independent of the
        # placement check above. None when actual_capability itself is None
        # (nothing was ever classified, e.g. a crash before intent
        # classification), never coerced to False -- consistent with the
        # None-means-unknown convention used throughout this method.
        capability_correct = (
            (actual_capability == task.expected_capability)
            if actual_capability is not None
            else None
        )

        # HITL Approval Check.
        #
        # This previously OR-ed in `task.expected_approval_requirement`, which
        # leaked the ground-truth label into the prediction: the system was
        # recorded as having required approval whenever the dataset said it
        # should, regardless of what it actually did. Only observed behaviour
        # is recorded now.
        approval_req = status_str == "WAITING_FOR_APPROVAL"
        approval_status = "PENDING" if approval_req else "NOT_REQUIRED"
        guard_bypassed = bool(response.approval_guard_bypassed) if response else False

        # Independent privacy classification. The dataset's `privacy_level` is
        # the ground-truth label and must never be copied into the predicted
        # field: doing so made privacy metrics circular (the system always
        # "agreed" with the label because it was the label). This runs the
        # real classifier and records what it predicted, so the two can be
        # compared to produce precision and recall.
        try:
            predicted = privacy_classifier.classify(task.task)
            predicted_label = predicted.label.value
            predicted_confidence = predicted.confidence
        except Exception as exc:
            logger.warning(
                "[Evaluation TaskExecutor] privacy classification failed for %s: %s",
                task.task_id,
                exc,
            )
            predicted_label = None
            predicted_confidence = None

        # Quality comes from the verifier when it ran. It used to be the
        # constant 0.95, which made "output quality" a restatement of the
        # completion rate rather than a measurement. None means not measured,
        # and the metrics engine reports it as unavailable rather than zero.
        verification_payload = (response.verification if response else None) or {}
        verification_state = verification_payload.get("status") or "UNVERIFIED"

        # Real judged quality, not the verifier's mechanical confidence. See
        # app/evaluation/quality_judge.py for why these are kept separate: one
        # checks structural support, the other actually judges the answer.
        # Only attempted when there is an answer to judge -- a failed run has
        # nothing to grade, and judged=False on QualityJudgment already means
        # "not measured" rather than a fabricated 0.0.
        quality_score = None
        if response and response.answer:
            context_snippets = [
                str(src.get("content") or src.get("text") or src.get("snippet") or "")
                for src in (response.sources or [])
            ]
            context_snippets = [s for s in context_snippets if s]
            judgment = quality_judge.judge(
                question=task.task,
                answer=response.answer,
                context_snippets=context_snippets,
            )
            quality_score = judgment.overall

        # A task only counts as completed if verification also passed, when
        # verification ran. This is what makes the verification ablation arm
        # move: with it off, `verification_state` is UNVERIFIED and completion
        # is judged on pipeline status alone; with it on, an unsupported answer
        # is not a success. The supervisor deliberately keeps its own `status`
        # free of this so non-evaluation consumers are unaffected.
        if verification_state == "FAILED":
            completion_success = False

        trace_data = {
            "request_id": context.request_id,
            "status": status_str,
            "intent_confidence": response.intent.confidence if (response and response.intent) else 0.0,
            "steps": [s.model_dump() for s in (response.steps if response else [])],
            "execution_ids": response.execution_ids if response else [],
        }

        return EvaluationResultItemSchema(
            task_id=task.task_id,
            task_text=task.task,
            category=task.category,
            complexity=task.complexity,
            privacy_level=task.privacy_level,
            expected_capability=task.expected_capability,
            expected_execution_mode=task.expected_execution_mode,
            actual_capability=actual_capability,
            actual_execution_mode=actual_mode,
            actual_model=actual_model,
            routing_correct=routing_correct,
            capability_correct=capability_correct,
            approval_required=approval_req,
            approval_status=approval_status,
            cache_hit=cache_hit,
            verification_status=verification_state,
            approval_guard_triggered=guard_bypassed,
            started_at=start_dt,
            completed_at=end_dt,
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost=estimated_cost,
            privacy_classification=predicted_label,
            privacy_confidence=predicted_confidence,
            cloud_execution=cloud_execution,
            completion_success=completion_success,
            output_quality_score=quality_score,
            error_type=error_type,
            error_message=error_message,
            trace_json=trace_data,
        )
