import logging
from typing import Optional

from app.core.config import settings
from app.privacy.contracts import Placement, RoutingDecision
from app.privacy.router import privacy_router
from app.runtime.exceptions import RuntimePolicyError
from app.runtime.model_registry import model_registry
from app.schemas.runtime import RuntimeGenerateRequest, RuntimeMode

logger = logging.getLogger(__name__)


class RuntimePolicy:
    """
    Validates request parameters and resolves placement.

    Previously `auto` collapsed to a static default (`RUNTIME_DEFAULT_MODE`,
    itself "auto", which then fell through to "local"), so cloud was unreachable
    unless a caller named it explicitly and no routing decision was ever made.
    `auto` now goes through the privacy-constrained router.

    The privacy constraint is enforced for explicitly requested modes too, not
    only for `auto`. A caller asking for cloud execution of confidential content
    is refused rather than silently downgraded: downgrading would hide an
    attempted disclosure that an operator needs to see.
    """

    @staticmethod
    def validate_request(
        request: RuntimeGenerateRequest,
    ) -> tuple[str, str, float, int, float, Optional[RoutingDecision]]:
        """
        Returns (mode, model, temperature, max_tokens, timeout, routing_decision).

        `routing_decision` is present when the router ran and None when the
        caller pinned local. Callers persist it as the audit record for why the
        request went where it did.
        """
        # 1. Validate prompt
        if not request.prompt or not request.prompt.strip():
            raise RuntimePolicyError("Prompt content cannot be empty.")

        # 2. Validate runtime mode
        mode_val = (
            request.execution_mode.value
            if isinstance(request.execution_mode, RuntimeMode)
            else (request.execution_mode or "auto")
        )
        clean_mode = str(mode_val).lower().strip()
        if clean_mode not in ("auto", "local", "cloud"):
            raise RuntimePolicyError(
                f"Invalid execution_mode '{clean_mode}'. Must be 'auto', 'local', or 'cloud'."
            )

        metadata = request.metadata or {}

        # Classify the user's data, not the prompt scaffolding around it.
        #
        # Handlers assemble prompts like "Please provide a concise summary of the
        # following document: <content>". Embedding that whole string drags the
        # classification toward whichever exemplars share the instruction
        # wording rather than the subject matter, so a public document wrapped
        # in a summarise instruction was landing near the "Summarize the Q3
        # payroll" exemplar. Handlers that know the raw content pass it here.
        classification_target = metadata.get("classification_content") or request.prompt

        # Evaluation-only escape hatch. The ALWAYS_CLOUD baseline has to be able
        # to route sensitive tasks to cloud, otherwise it is not a baseline and
        # the privacy comparison has nothing to compare against. Never set from
        # a user-facing path; logged at WARNING so its use is always visible.
        max_cloud_override = metadata.get("privacy_max_cloud_label")
        if max_cloud_override:
            logger.warning(
                "[RuntimePolicy] privacy constraint overridden to max_cloud_label=%r "
                "(request_id=%s). This must only originate from the evaluation harness.",
                max_cloud_override,
                request.request_id,
            )

        decision: Optional[RoutingDecision] = None

        if clean_mode == "auto":
            decision = privacy_router.route(
                content=classification_target,
                context=metadata,
                est_output_tokens=request.max_tokens or settings.ROUTER_DEFAULT_OUTPUT_TOKENS,
                latency_budget_ms=metadata.get("latency_budget_ms"),
                quality_floor=metadata.get("quality_floor"),
                max_cloud_label=max_cloud_override,
            )
            resolved_mode = decision.placement.value
            resolved_model = decision.model
            logger.info(
                "[RuntimePolicy] auto -> %s (%s): %s",
                resolved_mode,
                resolved_model,
                decision.reason,
            )
        else:
            resolved_mode = clean_mode
            # An explicitly pinned mode still has to satisfy the hard
            # constraint. Local is always permitted, so only cloud is checked;
            # this keeps the classifier off the hot path for local requests.
            if resolved_mode == "cloud" and not settings.RUNTIME_CLOUD_ENABLED:
                raise RuntimePolicyError(
                    "Cloud execution is disabled in this deployment "
                    "(RUNTIME_CLOUD_ENABLED=false). Set it to true and configure "
                    "OPENROUTER_API_KEY to restore hybrid execution. Refusing "
                    "rather than silently downgrading to local, so a caller that "
                    "explicitly asked for cloud is never told it got one."
                )
            if resolved_mode == "cloud":
                probe = privacy_router.route(
                    content=classification_target,
                    context=metadata,
                    est_output_tokens=request.max_tokens
                    or settings.ROUTER_DEFAULT_OUTPUT_TOKENS,
                    max_cloud_label=max_cloud_override,
                )
                if Placement.CLOUD not in probe.allowed_placements:
                    raise RuntimePolicyError(
                        "Cloud execution refused: content classified "
                        f"'{probe.classification.label.value}' "
                        f"(confidence {probe.classification.confidence:.2f}, "
                        f"stage {probe.classification.stage.value}). "
                        "Sensitive content does not leave local execution."
                    )
                decision = probe
            resolved_model = request.model or ""

        # 3. Model allowlist
        resolved_model = model_registry.validate_model(resolved_model, resolved_mode)

        # 4. Temperature bounds [0.0, 2.0]
        temp = request.temperature if request.temperature is not None else 0.2
        if not (0.0 <= temp <= 2.0):
            raise RuntimePolicyError(f"Temperature {temp} out of allowed range [0.0, 2.0].")

        # 5. Max tokens limit
        tokens = request.max_tokens if request.max_tokens is not None else 1024
        clean_tokens = min(max(1, tokens), settings.RUNTIME_MAX_TOKENS)

        # 6. Timeout cap
        t_out = request.timeout if request.timeout is not None else settings.RUNTIME_TIMEOUT
        clean_timeout = min(max(1.0, t_out), settings.RUNTIME_MAX_TIMEOUT)

        return resolved_mode, resolved_model, temp, clean_tokens, clean_timeout, decision


runtime_policy = RuntimePolicy()
