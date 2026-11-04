import uuid
"""
Commitment Service: Full lifecycle, ownership, verification, and analytics
over app/models/commitment.py, commitment_events, and WorkGraph integrations.
"""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from sqlalchemy import or_, and_, func
from sqlalchemy.orm import Session

from app.models.commitment import Commitment
from app.models.commitment_event import CommitmentEvent
from app.models.workgraph import Task
from app.models.work_ai import AiProposal
from app.utils.date_parser import parse_deadline
from app.utils.timezone import local_now, resolve_timezone

logger = logging.getLogger(__name__)

AT_RISK_WINDOW_DAYS = 2


def _compute_effective_status(
    stored_status: str,
    normalized_due_date: Optional[datetime],
    due_date_str: Optional[str],
    linked_task: Optional[Task],
) -> str:
    """
    Computes effective operational status:
    - 'completed' if marked completed or linked task is done
    - 'dismissed' if dismissed
    - 'overdue' if past due date and not completed
    - 'at_risk' if due within AT_RISK_WINDOW_DAYS
    - 'pending' otherwise
    """
    if stored_status in ("completed", "dismissed"):
        return stored_status

    if linked_task is not None and linked_task.status == "done":
        return "completed"

    now = datetime.now(timezone.utc)
    target_due: Optional[datetime] = None

    if linked_task is not None and linked_task.due_date is not None:
        task_due = linked_task.due_date
        target_due = task_due if task_due.tzinfo else task_due.replace(tzinfo=timezone.utc)
    elif normalized_due_date is not None:
        target_due = (
            normalized_due_date
            if normalized_due_date.tzinfo
            else normalized_due_date.replace(tzinfo=timezone.utc)
        )
    elif due_date_str:
        parsed = parse_deadline(due_date_str)
        if parsed.normalized_dt:
            target_due = parsed.normalized_dt

    if target_due is not None:
        if target_due < now:
            return "overdue"
        if target_due < now + timedelta(days=AT_RISK_WINDOW_DAYS):
            return "at_risk"

    return "pending"


class CommitmentService:

    @staticmethod
    def record_event(
        db: Session,
        commitment_id: str,
        owner_id: str,
        event_type: str,
        actor_id: Optional[str] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> CommitmentEvent:
        event = CommitmentEvent(
            commitment_id=commitment_id,
            owner_id=owner_id,
            event_type=event_type,
            actor_id=actor_id or owner_id,
            details=json.dumps(details or {}),
        )
        db.add(event)
        try:
            db.commit()
            db.refresh(event)
        except Exception as e:
            logger.warning("[CommitmentService] Failed to record event: %s", e)
            db.rollback()
        return event

    @staticmethod
    def upsert_commitment(
        db: Session,
        owner_id: str,
        description: str,
        source_type: str,
        source_ref: str,
        responsible_party: Optional[str] = None,
        due_date: Optional[str] = None,
        linked_task_id: Optional[str] = None,
        counterparty: Optional[str] = None,
        direction: Optional[str] = None,
        evidence: Optional[str] = None,
        confidence: Optional[float] = None,
        priority: Optional[str] = None,
        source_metadata: Optional[dict[str, Any]] = None,
        user_tz: Optional[str] = "UTC",
    ) -> tuple[Commitment, bool]:
        """
        Upserts commitment keyed on (owner_id, source_type, source_ref).
        Normalizes deadlines and tracks lifecycle history. Returns (row, created).
        """
        linked_task = None
        if linked_task_id:
            linked_task = db.query(Task).filter(Task.id == linked_task_id, Task.owner_id == owner_id).first()

        parsed = parse_deadline(due_date, user_tz=user_tz)
        normalized_dt = parsed.normalized_dt

        effective_status = _compute_effective_status(
            stored_status="pending",
            normalized_due_date=normalized_dt,
            due_date_str=due_date,
            linked_task=linked_task,
        )
        status_to_store = effective_status

        dir_val = (direction or "owed_by_me").strip().lower()
        if dir_val not in ("owed_by_me", "owed_to_me", "mutual", "unknown"):
            dir_val = "owed_by_me"

        prio_val = (priority or "medium").strip().lower()
        if prio_val not in ("low", "medium", "high"):
            prio_val = "medium"

        existing = (
            db.query(Commitment)
            .filter(
                Commitment.owner_id == owner_id,
                Commitment.source_type == source_type,
                Commitment.source_ref == source_ref,
            )
            .first()
        )

        metadata_str = json.dumps(source_metadata) if source_metadata else None

        if existing:
            # Preserve completed / dismissed manual status
            if existing.status in ("completed", "dismissed"):
                status_to_store = existing.status

            existing.description = description
            existing.responsible_party = responsible_party or existing.responsible_party
            existing.counterparty = counterparty or existing.counterparty
            existing.direction = dir_val or existing.direction
            existing.due_date = due_date
            existing.original_due_date_text = due_date
            existing.normalized_due_date = normalized_dt or existing.normalized_due_date
            existing.evidence = evidence or existing.evidence
            if confidence is not None:
                existing.confidence = confidence
            existing.priority = prio_val
            existing.linked_task_id = linked_task_id or existing.linked_task_id
            existing.status = status_to_store
            if metadata_str:
                existing.source_metadata = metadata_str

            db.commit()
            db.refresh(existing)

            CommitmentService.record_event(
                db, existing.id, owner_id, "updated", details={"source_type": source_type, "source_ref": source_ref}
            )
            return existing, False

        row = Commitment(
            owner_id=owner_id,
            description=description,
            responsible_party=responsible_party,
            counterparty=counterparty,
            direction=dir_val,
            due_date=due_date,
            original_due_date_text=due_date,
            normalized_due_date=normalized_dt,
            timezone=user_tz or "UTC",
            confidence=confidence if confidence is not None else 1.0,
            evidence=evidence,
            priority=prio_val,
            source_type=source_type,
            source_ref=source_ref,
            source_metadata=metadata_str,
            status=status_to_store,
            linked_task_id=linked_task_id,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        CommitmentService.record_event(
            db, row.id, owner_id, "created", details={"source_type": source_type, "source_ref": source_ref}
        )
        return row, True

    @staticmethod
    def create_commitment(
        db: Session,
        owner_id: str,
        description: str,
        responsible_party: Optional[str] = None,
        counterparty: Optional[str] = None,
        direction: str = "owed_by_me",
        due_date: Optional[str] = None,
        priority: str = "medium",
        evidence: Optional[str] = None,
        source_type: str = "manual",
        source_ref: Optional[str] = None,
        user_tz: Optional[str] = "UTC",
    ) -> Commitment:
        ref = source_ref or f"man_{uuid.uuid4().hex[:10]}"
        row, _ = CommitmentService.upsert_commitment(
            db=db,
            owner_id=owner_id,
            description=description,
            source_type=source_type,
            source_ref=ref,
            responsible_party=responsible_party,
            counterparty=counterparty,
            direction=direction,
            due_date=due_date,
            priority=priority,
            evidence=evidence,
            user_tz=user_tz,
        )
        return row

    @staticmethod
    def get_commitment(db: Session, commitment_id: str, owner_id: str) -> Optional[Commitment]:
        return (
            db.query(Commitment)
            .filter(Commitment.id == commitment_id, Commitment.owner_id == owner_id)
            .first()
        )

    @staticmethod
    def update_commitment(
        db: Session,
        commitment_id: str,
        owner_id: str,
        updates: dict[str, Any],
        user_tz: Optional[str] = "UTC",
    ) -> Optional[Commitment]:
        c = CommitmentService.get_commitment(db, commitment_id, owner_id)
        if not c:
            return None

        details: dict[str, Any] = {}
        if "description" in updates and updates["description"]:
            details["old_description"] = c.description
            c.description = updates["description"]
            details["new_description"] = c.description

        if "responsible_party" in updates:
            details["old_owner"] = c.responsible_party
            c.responsible_party = updates["responsible_party"]
            details["new_owner"] = c.responsible_party

        if "counterparty" in updates:
            details["old_counterparty"] = c.counterparty
            c.counterparty = updates["counterparty"]
            details["new_counterparty"] = c.counterparty

        if "direction" in updates and updates["direction"]:
            c.direction = updates["direction"]

        if "due_date" in updates and updates["due_date"] is not None:
            details["old_due_date"] = c.due_date
            c.due_date = updates["due_date"]
            c.original_due_date_text = updates["due_date"]
            parsed = parse_deadline(updates["due_date"], user_tz=user_tz)
            c.normalized_due_date = parsed.normalized_dt
            details["new_due_date"] = c.due_date

        if "priority" in updates and updates["priority"]:
            c.priority = updates["priority"]

        if "status" in updates and updates["status"]:
            details["old_status"] = c.status
            c.status = updates["status"]
            details["new_status"] = c.status

        if "verification_status" in updates and updates["verification_status"]:
            c.verification_status = updates["verification_status"]

        if "verification_evidence" in updates:
            c.verification_evidence = updates["verification_evidence"]

        if "verification_reasoning" in updates:
            c.verification_reasoning = updates["verification_reasoning"]

        if "linked_task_id" in updates:
            c.linked_task_id = updates["linked_task_id"]

        db.commit()
        db.refresh(c)
        CommitmentService.record_event(db, c.id, owner_id, "updated", details=details)
        return c

    @staticmethod
    def complete_commitment(db: Session, commitment_id: str, owner_id: str) -> Optional[Commitment]:
        c = CommitmentService.get_commitment(db, commitment_id, owner_id)
        if not c:
            return None
        c.status = "completed"
        c.verification_status = "verified"
        db.commit()
        db.refresh(c)
        CommitmentService.record_event(db, c.id, owner_id, "completed")
        return c

    @staticmethod
    def dismiss_commitment(db: Session, commitment_id: str, owner_id: str) -> Optional[Commitment]:
        c = CommitmentService.get_commitment(db, commitment_id, owner_id)
        if not c:
            return None
        c.status = "dismissed"
        db.commit()
        db.refresh(c)
        CommitmentService.record_event(db, c.id, owner_id, "dismissed")
        return c

    @staticmethod
    def reopen_commitment(db: Session, commitment_id: str, owner_id: str) -> Optional[Commitment]:
        c = CommitmentService.get_commitment(db, commitment_id, owner_id)
        if not c:
            return None
        c.status = "pending"
        c.verification_status = "unverified"
        db.commit()
        db.refresh(c)
        CommitmentService.record_event(db, c.id, owner_id, "reopened")
        return c

    @staticmethod
    def verify_commitment(
        db: Session,
        commitment_id: str,
        owner_id: str,
        verification_status: Optional[str] = None,
        evidence: Optional[str] = None,
        reasoning: Optional[str] = None,
    ) -> Optional[Commitment]:
        c = CommitmentService.get_commitment(db, commitment_id, owner_id)
        if not c:
            return None

        # Check linked task evidence
        if not verification_status and c.linked_task_id:
            task = db.query(Task).filter(Task.id == c.linked_task_id, Task.owner_id == owner_id).first()
            if task and task.status == "done":
                verification_status = "verified"
                evidence = f"Linked WorkGraph task '{task.title}' was marked done."
                reasoning = "Completion verified via linked task completion."

        final_status = verification_status or "verified"
        c.verification_status = final_status
        if evidence:
            c.verification_evidence = evidence
        if reasoning:
            c.verification_reasoning = reasoning

        if final_status == "verified":
            c.status = "completed"

        db.commit()
        db.refresh(c)
        CommitmentService.record_event(
            db, c.id, owner_id, "verified", details={"status": final_status, "evidence": evidence}
        )
        return c

    @staticmethod
    def list_commitments(
        db: Session,
        owner_id: str,
        status: Optional[str] = None,
        direction: Optional[str] = None,
        source_type: Optional[str] = None,
        search: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Commitment]:
        query = db.query(Commitment).filter(Commitment.owner_id == owner_id)

        if direction and direction != "all":
            query = query.filter(Commitment.direction == direction)

        if source_type and source_type != "all":
            query = query.filter(Commitment.source_type == source_type)

        if priority and priority != "all":
            query = query.filter(Commitment.priority == priority)

        if search and search.strip():
            term = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    Commitment.description.ilike(term),
                    Commitment.responsible_party.ilike(term),
                    Commitment.counterparty.ilike(term),
                    Commitment.evidence.ilike(term),
                )
            )

        items = query.order_by(Commitment.created_at.desc()).all()

        # Resolve effective statuses and apply status filter
        enriched = []
        for item in items:
            linked_task = None
            if item.linked_task_id:
                linked_task = db.query(Task).filter(Task.id == item.linked_task_id).first()

            eff_status = _compute_effective_status(
                stored_status=item.status,
                normalized_due_date=item.normalized_due_date,
                due_date_str=item.due_date,
                linked_task=linked_task,
            )
            item.effective_status = eff_status

            if status and status != "all":
                if status in ("at_risk", "overdue"):
                    if eff_status != status:
                        continue
                elif status == "pending":
                    # Pending matches items that are not completed/dismissed
                    if eff_status not in ("pending", "at_risk", "overdue"):
                        continue
                elif item.status != status and eff_status != status:
                    continue

            enriched.append(item)

        return enriched[offset : offset + limit]

    @staticmethod
    def get_stats(db: Session, owner_id: str) -> dict[str, Any]:
        all_items = db.query(Commitment).filter(Commitment.owner_id == owner_id).all()

        total = len(all_items)
        completed = 0
        dismissed = 0
        pending = 0
        at_risk = 0
        overdue = 0
        owed_by_me = 0
        owed_to_me = 0
        mutual = 0
        unknown = 0
        awaiting_others = 0
        newly_discovered_this_week = 0

        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        for item in all_items:
            # Creation timing
            created = item.created_at
            if created:
                created_utc = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
                if created_utc >= one_week_ago:
                    newly_discovered_this_week += 1

            # Direction
            direction = item.direction or "owed_by_me"
            if direction == "owed_by_me":
                owed_by_me += 1
            elif direction == "owed_to_me":
                owed_to_me += 1
            elif direction == "mutual":
                mutual += 1
            else:
                unknown += 1

            # Effective status
            eff = _compute_effective_status(
                stored_status=item.status,
                normalized_due_date=item.normalized_due_date,
                due_date_str=item.due_date,
                linked_task=None,
            )

            if eff == "completed":
                completed += 1
            elif eff == "dismissed":
                dismissed += 1
            elif eff == "overdue":
                overdue += 1
                pending += 1
                if direction == "owed_to_me":
                    awaiting_others += 1
            elif eff == "at_risk":
                at_risk += 1
                pending += 1
                if direction == "owed_to_me":
                    awaiting_others += 1
            else:
                pending += 1
                if direction == "owed_to_me":
                    awaiting_others += 1

        active_total = total - dismissed
        completion_rate = round((completed / active_total * 100), 1) if active_total > 0 else 0.0

        return {
            "total": total,
            "pending": pending,
            "at_risk": at_risk,
            "overdue": overdue,
            "completed": completed,
            "dismissed": dismissed,
            "completion_rate": completion_rate,
            "newly_discovered_this_week": newly_discovered_this_week,
            "awaiting_others": awaiting_others,
            "owed_by_me": owed_by_me,
            "owed_to_me": owed_to_me,
            "mutual": mutual,
            "unknown": unknown,
        }

    @staticmethod
    def get_analytics(db: Session, owner_id: str) -> dict[str, Any]:
        stats = CommitmentService.get_stats(db, owner_id)
        all_items = db.query(Commitment).filter(Commitment.owner_id == owner_id).all()

        source_dist: dict[str, int] = {}
        priority_dist: dict[str, int] = {}
        counterparty_counts: dict[str, int] = {}

        for item in all_items:
            src = item.source_type or "unknown"
            source_dist[src] = source_dist.get(src, 0) + 1

            prio = item.priority or "medium"
            priority_dist[prio] = priority_dist.get(prio, 0) + 1

            cp = (item.counterparty or item.responsible_party or "").strip()
            if cp:
                counterparty_counts[cp] = counterparty_counts.get(cp, 0) + 1

        top_counterparties = [
            {"name": name, "count": count}
            for name, count in sorted(counterparty_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
        ]

        # Actionable insights
        actionable_insights = []
        if stats["overdue"] > 0:
            actionable_insights.append({
                "type": "risk",
                "title": f"{stats['overdue']} Overdue Commitment{'s' if stats['overdue'] != 1 else ''}",
                "detail": "Action items or promises have breached their target deadlines. Send reminders or renegotiate deadlines.",
            })
        if stats["awaiting_others"] > 0:
            actionable_insights.append({
                "type": "follow_up",
                "title": f"{stats['awaiting_others']} Deliverables Awaiting Others",
                "detail": "Counterparties owe deliverables or updates. Use Follow-Up Center to draft gentle reminder emails.",
            })
        if stats["completion_rate"] >= 80.0 and stats["total"] >= 5:
            actionable_insights.append({
                "type": "positive",
                "title": f"High Delivery Rate ({stats['completion_rate']}%)",
                "detail": "Commitments are being fulfilled on schedule with low carry-over risk.",
            })
        elif stats["completion_rate"] < 50.0 and stats["total"] >= 5:
            actionable_insights.append({
                "type": "warning",
                "title": f"Delivery Rate Lagging ({stats['completion_rate']}%)",
                "detail": "More than half of active commitments remain pending or delayed.",
            })

        return {
            "stats": stats,
            "status_distribution": {
                "completed": stats["completed"],
                "pending": stats["pending"],
                "at_risk": stats["at_risk"],
                "overdue": stats["overdue"],
                "dismissed": stats["dismissed"],
            },
            "direction_distribution": {
                "owed_by_me": stats["owed_by_me"],
                "owed_to_me": stats["owed_to_me"],
                "mutual": stats["mutual"],
                "unknown": stats["unknown"],
            },
            "source_distribution": source_dist,
            "priority_distribution": priority_dist,
            "top_counterparties": top_counterparties,
            "actionable_insights": actionable_insights,
        }

    @staticmethod
    def generate_follow_up(db: Session, commitment_id: str, owner_id: str) -> dict[str, Any]:
        c = CommitmentService.get_commitment(db, commitment_id, owner_id)
        if not c:
            raise ValueError("Commitment not found")

        if c.direction == "owed_to_me":
            recipient = c.responsible_party or c.counterparty or "Colleague"
        else:
            recipient = c.counterparty or c.responsible_party or "Colleague"
        deadline_text = c.original_due_date_text or c.due_date or "recently"

        subject = f"Friendly Follow-up: {c.description[:50]}"
        body = (
            f"Hi {recipient},\n\n"
            f"I hope you're doing well. Just following up regarding: '{c.description}', "
            f"which was targeted for completion around {deadline_text}.\n\n"
            f"Could you please share a quick update when you have a moment? Let me know if you need any input or support.\n\n"
            f"Thanks,\n"
        )

        CommitmentService.record_event(
            db, c.id, owner_id, "follow_up_generated", details={"recipient": recipient, "subject": subject}
        )

        return {
            "commitment_id": c.id,
            "counterparty": recipient,
            "suggested_follow_up_date": datetime.now(timezone.utc).date().isoformat(),
            "reason": f"Deliverable '{c.description}' is pending/overdue with target deadline '{deadline_text}'.",
            "subject": subject,
            "body": body,
        }

    @staticmethod
    def propose_task(
        db: Session,
        commitment_id: str,
        owner_id: str,
        user_email: Optional[str] = None,
    ) -> dict[str, Any]:
        c = CommitmentService.get_commitment(db, commitment_id, owner_id)
        if not c:
            raise ValueError("Commitment not found")

        # Check if already proposed in AiProposal
        existing = (
            db.query(AiProposal)
            .filter(
                AiProposal.owner_id == owner_id,
                AiProposal.source == "commitment",
                AiProposal.source_ref == c.id,
                AiProposal.status == "PENDING",
            )
            .first()
        )
        if existing:
            return {
                "proposal_id": existing.id,
                "status": "already_exists",
                "message": "Task proposal already pending in AI Inbox",
            }

        # Create proposal in AI Inbox
        payload = {
            "title": c.description[:255],
            "description": f"Created from commitment (ref: {c.source_ref}). Evidence: {c.evidence or 'None'}",
            "due_date": c.normalized_due_date.isoformat() if c.normalized_due_date else c.due_date,
            "priority": c.priority or "medium",
            "type": "task",
        }
        proposal = AiProposal(
            owner_id=owner_id,
            kind="create_item",
            agent="CommitmentAgent",
            payload=payload,
            source="commitment",
            source_ref=c.id,
            status="PENDING",
            confidence=c.confidence or 0.9,
            explanation=f"Proposing task to track commitment '{c.description}' with deadline {c.due_date or 'unspecified'}.",
            autonomy_level="L1",
        )
        db.add(proposal)
        db.commit()
        db.refresh(proposal)

        CommitmentService.record_event(
            db, c.id, owner_id, "task_linked", details={"proposal_id": proposal.id}
        )

        return {
            "proposal_id": proposal.id,
            "status": "created",
            "message": "Task proposal created in AI Inbox for approval",
        }


commitment_service = CommitmentService()
