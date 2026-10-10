import uuid
from dataclasses import dataclass, field
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.supervisor.blackboard import RunBlackboard


@dataclass
class SupervisorContext:
    owner_id: str
    question: str
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:10]}")
    trace_id: str = field(default_factory=lambda: f"trace_{uuid.uuid4().hex[:12]}")
    execution_mode: str = "auto"
    timeout: float = 60.0
    conversation_id: Optional[str] = None
    # Set when the user asked about one specific document. Reachable from a
    # plan step as $context.file_id.
    file_id: Optional[str] = None

    # Component toggles. These were previously passed as metadata strings by
    # the evaluation harness and read by nothing, which made every ablation arm
    # behave identically. They are typed fields now and each one is consulted
    # on a real branch: `cache_enabled` in the execution executor,
    # `hitl_enabled` and `verification_enabled` in the supervisor run loop.
    #
    # Defaults are True so production behaviour is the full stack; only the
    # ablation harness turns them off.
    cache_enabled: bool = True
    verification_enabled: bool = True
    hitl_enabled: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)

    # Phase 24: the run's shared working memory, constructed by the
    # supervisor per-run (never a global/shared instance) once the plan's
    # run id is known. Reachable from a plan step as $state.<key>. Optional
    # so legacy callers that build a SupervisorContext directly (without
    # going through amof_supervisor.run) keep working -- resolve_step_input
    # fails closed to None for $state.* when this is unset, exactly like the
    # existing $step.* branch does for a missing dependency.
    blackboard: Optional["RunBlackboard"] = None

    def resolve_user_id(self) -> int:
        """
        The integer `users.id` this run acts on behalf of.

        `owner_id` is a string throughout the execution layer — `Execution.owner_id`
        is a String column and retrieval scopes on it as an opaque tenant key — but
        `Approval.user_id` is an integer FK to `users.id`. The conversion has to
        happen somewhere.

        It used to happen silently: `int(owner_id) if owner_id.isdigit() else 1`.
        A non-numeric owner_id filed the approval against **user 1**, and because
        the workspace id is derived from the same value, it landed in user 1's
        workspace too — invisible to the real requester and approvable by the
        wrong person. An owner_id that isn't a user id is a programming error,
        not a value to guess at.
        """
        try:
            return int(self.owner_id)
        except (TypeError, ValueError):
            raise ValueError(
                f"owner_id {self.owner_id!r} is not a users.id, so this run cannot "
                "file an approval: there is no way to tell whose approval it is."
            ) from None

    @property
    def workspace_id(self) -> str:
        """
        Derived from `resolve_user_id` rather than computed separately, so the
        approval's owner and its workspace cannot disagree.
        """
        return f"ws_user_{self.resolve_user_id()}"
