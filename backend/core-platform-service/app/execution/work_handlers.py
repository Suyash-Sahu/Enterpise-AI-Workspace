"""
AMOF Work mutation capabilities (PRD v3 §6.1).

These are the ONLY code paths through which AI output changes WorkGraph, and
each is `requires_human_approval=True`: the executor refuses to reach
`execute()` unless it atomically claims a real, approved Approval row. On top
of that, each handler:

  * loads the AiProposal and requires it to belong to the executing owner, to
    still be PENDING/APPROVED (never CANCELLED/REJECTED/EXPIRED), and to be the
    proposal that owns *this* approval;
  * re-checks the kill switch at the moment of mutation (so an approval granted
    before the switch flipped cannot execute after it);
  * re-validates the approved payload (which the generic /approvals edit
    endpoint lets a user change) against owner_id and whitelists its fields;
  * takes provenance (agent, source_ref, ai_confidence) from the proposal row,
    never from the payload;
  * verifies its own effect before marking the proposal EXECUTED.

Imports of app.services.work_ai.pipeline are lazy: the registry imports this
module, and the pipeline imports the executor (which imports the registry).
"""
from typing import Any

from sqlalchemy.orm import Session

from app.execution.contracts import CapabilityMetadata, ExecutionContext, ExecutionHandler
from app.models.work_ai import AiProposal
from app.schemas.workgraph import TaskCreate
from app.services.work_ai import guard
from app.services.workgraph_service import workgraph_service


class _WorkMutationHandler(ExecutionHandler):
    kind: str  # the AiProposal.kind this capability performs

    def _load(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> AiProposal:
        prop = (
            db.query(AiProposal)
            .filter(AiProposal.id == input_data.get("proposal_id"), AiProposal.owner_id == context.owner_id)
            .first()
        )
        if prop is None:
            raise PermissionError("No matching AI proposal for this execution.")
        if prop.kind != self.kind:
            raise PermissionError("Proposal kind does not match this capability.")
        if prop.status not in ("PENDING", "APPROVED"):
            raise PermissionError(f"Proposal is {prop.status}; refusing to execute.")
        if prop.approval_id is None or context.metadata.get("approval_id") != prop.approval_id:
            raise PermissionError("Approval does not belong to this proposal.")
        guard.assert_enabled(db, context.owner_id, prop.project_id)  # KillSwitchOff
        return prop

    def _clean(self, db: Session, prop: AiProposal, input_data: dict[str, Any]) -> dict[str, Any]:
        from app.services.work_ai.pipeline import normalize_payload

        clean, project_id = normalize_payload(
            db, prop.owner_id, self.kind, {k: v for k, v in input_data.items() if k != "proposal_id"}
        )
        if project_id != prop.project_id:
            raise PermissionError("Approved payload changed the proposal's project scope.")
        return clean

    @staticmethod
    def _finish(db: Session, prop: AiProposal, result: dict[str, Any]) -> dict[str, Any]:
        prop.status = "EXECUTED"
        prop.result = result
        prop.error = None
        db.commit()
        return {"result": result, "provider": "workgraph", "model": None}


class CreateItemHandler(_WorkMutationHandler):
    kind = "create_item"
    metadata = CapabilityMetadata(
        description="Creates a WorkGraph item from an approved AI proposal (agent/source/confidence recorded).",
        risk_level="medium",
        side_effect="reversible_write",
        requires_verification=False,
        requires_human_approval=True,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        prop = self._load(db, context, input_data)
        data = TaskCreate(**self._clean(db, prop, input_data))
        task = workgraph_service.create_task(
            db,
            prop.owner_id,
            data.title,
            description=data.description,
            project_id=data.project_id,
            assignee=data.assignee,
            priority=data.priority,
            status=data.status,
            type=data.type,
            due_date=data.due_date,
            created_by="ai",
            created_by_actor=f"agent:{prop.agent}",
            source_type="ai_proposal",
            source_ref=prop.id,
            ai_confidence=prop.confidence,
            depends_on=data.depends_on,
        )
        made = workgraph_service.get_task(db, prop.owner_id, task.id)  # verification
        if made is None or made.source_ref != prop.id or made.created_by != "ai":
            raise RuntimeError("Verification failed: created item is missing or lacks AI provenance.")
        return self._finish(db, prop, {"task_id": task.id})


class UpdateItemHandler(_WorkMutationHandler):
    kind = "update_item"
    metadata = CapabilityMetadata(
        description="Updates a WorkGraph item from an approved AI proposal (change recorded in the activity trail).",
        risk_level="medium",
        side_effect="reversible_write",
        requires_verification=False,
        requires_human_approval=True,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        prop = self._load(db, context, input_data)
        clean = self._clean(db, prop, input_data)
        task_id = clean.pop("task_id")
        task = workgraph_service.update_task(
            db, prop.owner_id, task_id,
            actor=f"agent:{prop.agent}", ai_confidence=prop.confidence, source_ref=prop.id, **clean,
        )
        if task is None:
            raise RuntimeError("Verification failed: item not found after update.")
        return self._finish(db, prop, {"task_id": task.id, "changed": sorted(clean)})


class LinkItemsHandler(_WorkMutationHandler):
    kind = "link_items"
    metadata = CapabilityMetadata(
        description="Links two WorkGraph items (cycle/ownership-checked) from an approved AI proposal.",
        risk_level="medium",
        side_effect="reversible_write",
        requires_verification=False,
        requires_human_approval=True,
    )

    def execute(self, db: Session, context: ExecutionContext, input_data: dict[str, Any]) -> dict[str, Any]:
        prop = self._load(db, context, input_data)
        clean = self._clean(db, prop, input_data)
        dep = workgraph_service.add_dependency(
            db, prop.owner_id, clean["task_id"], clean["other_task_id"],
            kind=clean["link_kind"], actor=f"agent:{prop.agent}", source_ref=prop.id,
        )
        return self._finish(db, prop, {"task_id": dep.task_id, "other_task_id": dep.depends_on_task_id, "kind": dep.kind})
