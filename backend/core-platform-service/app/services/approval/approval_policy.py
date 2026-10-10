"""
Project 8 — Approval Policy Engine
Determines whether a proposed action requires Human-in-the-Loop approval
and assigns deterministic risk levels.

AMOF-X Phase 5: for any capability actually registered in TaskRegistry, its
declared CapabilityMetadata (app/execution/contracts.py) is now the single
source of truth -- ACTION_POLICIES below previously duplicated it (a second,
hand-maintained "gmail.send": requires_approval=True entry sitting next to
the real one on GmailSendHandler.metadata, with no automated link between
them), exactly the kind of drift this project has already hit and fixed for
ALLOWED_CAPABILITIES (app/supervisor/policies.py) and the leak-rate SENSITIVE
set (app/evaluation/privacy_metrics.py). ACTION_POLICIES and the suffix
heuristic below now only apply to capabilities that don't exist in the
registry yet (calendar.create, webhook.post, data.delete -- future phases'
work), where there is no CapabilityMetadata to defer to.
"""

from typing import Dict, Any

from app.execution.registry import task_registry

ACTION_POLICIES: Dict[str, Dict[str, Any]] = {
    "calendar.create": {
        "risk_level": "high",
        "requires_approval": True,
        "description": "Schedule a new event on Google Calendar",
    },
    "calendar.update": {
        "risk_level": "medium",
        "requires_approval": True,
        "description": "Update an existing Google Calendar event",
    },
    "webhook.post": {
        "risk_level": "high",
        "requires_approval": True,
        "description": "Dispatch HTTP payload to an external webhook endpoint",
    },
    "data.delete": {
        "risk_level": "critical",
        "requires_approval": True,
        "description": "Permanent deletion of workspace data",
    },
}


class ApprovalPolicyEngine:
    @staticmethod
    def requires_approval(action_type: str) -> bool:
        """
        Check if an action_type requires HITL approval.
        Side-effect operations return True; internal read-only capabilities return False.
        """
        clean = action_type.lower().strip()
        if clean in task_registry.list_supported_tasks():
            return task_registry.get_metadata(clean).requires_human_approval

        policy = ACTION_POLICIES.get(clean)
        if policy is not None:
            return policy["requires_approval"]

        # Check if action is an external side-effect
        side_effect_suffixes = (".send", ".create", ".update", ".delete", ".post", ".put", ".remove")
        if any(clean.endswith(sfx) for sfx in side_effect_suffixes):
            return True

        return False

    @staticmethod
    def get_risk_level(action_type: str) -> str:
        """
        Get the risk level of an action_type ("low", "medium", "high", "critical").
        """
        clean = action_type.lower().strip()
        if clean in task_registry.list_supported_tasks():
            return task_registry.get_metadata(clean).risk_level

        policy = ACTION_POLICIES.get(clean)
        if policy is not None:
            return policy["risk_level"]
        return "high"

    @staticmethod
    def get_action_description(action_type: str) -> str:
        clean = action_type.lower().strip()
        if clean in task_registry.list_supported_tasks():
            return task_registry.get_metadata(clean).description

        policy = ACTION_POLICIES.get(clean)
        if policy is not None:
            return policy["description"]
        return f"Perform side-effect action {action_type}"


approval_policy = ApprovalPolicyEngine()
