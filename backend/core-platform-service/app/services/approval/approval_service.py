"""
Project 8 — Approval Core Service
Manages approval lifecycle, atomic state transitions, concurrency claims,
replay prevention, edit preservation, and execution authorization checks.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.core.config import settings
from app.events import Event, EventType, event_publisher
from app.models.approval import Approval
from app.models.approval_event import ApprovalEvent
from app.schemas.approval import ApprovalCreate, ApprovalEdit, ApprovalReject, ApprovalResponse
from app.services.approval.approval_policy import approval_policy
from app.services.approval.approval_audit import approval_audit


class ApprovalService:
    def create_approval(
        self,
        db: Session,
        user_id: int,
        workspace_id: str,
        data: ApprovalCreate,
        ttl_minutes: Optional[int] = None,
    ) -> Approval:
        """
        Creates a new pending approval record.
        """
        ttl = ttl_minutes or settings.APPROVAL_DEFAULT_TTL_MINUTES
        if ttl > settings.APPROVAL_MAX_TTL_MINUTES:
            ttl = settings.APPROVAL_MAX_TTL_MINUTES

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=ttl)
        risk = data.risk_level or approval_policy.get_risk_level(data.action_type)

        approval = Approval(
            user_id=user_id,
            workspace_id=workspace_id,
            execution_id=data.execution_id,
            action_type=data.action_type,
            status="pending",
            title=data.title,
            description=data.description,
            payload=data.payload,
            edited_payload=None,
            risk_level=risk,
            expires_at=expires_at,
            created_at=now,
            updated_at=now,
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)

        # Audit log creation event
        approval_audit.log_event(
            db=db,
            approval_id=approval.id,
            user_id=user_id,
            event_type="CREATED",
            old_status=None,
            new_status="pending",
            metadata_json={"action_type": data.action_type, "risk_level": risk},
        )

        event_publisher.publish(Event(
            event_type=EventType.APPROVAL_REQUESTED,
            owner_id=str(user_id),
            payload={"approval_id": approval.id, "action_type": data.action_type, "risk_level": risk},
        ))

        return approval

    def get_approval(self, db: Session, approval_id: int, user_id: int, workspace_id: str) -> Approval:
        """
        Fetch an approval record by ID. Verifies tenant and ownership isolation.
        Automatically invalidates expired records if pending.
        """
        approval = (
            db.query(Approval)
            .filter(
                Approval.id == approval_id,
                Approval.user_id == user_id,
                Approval.workspace_id == workspace_id,
            )
            .first()
        )
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval #{approval_id} not found or access denied",
            )

        self._check_and_update_expiration(db, approval)
        return approval

    def list_pending(
        self,
        db: Session,
        user_id: int,
        workspace_id: str,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Approval], int]:
        """
        List all pending non-expired approvals for the authenticated user and workspace.
        """
        now = datetime.now(timezone.utc)
        
        # Auto-expire any expired pending items first
        expired_items = (
            db.query(Approval)
            .filter(
                Approval.user_id == user_id,
                Approval.workspace_id == workspace_id,
                Approval.status == "pending",
                Approval.expires_at <= now,
            )
            .all()
        )
        for item in expired_items:
            item.status = "expired"
            db.add(item)
            approval_audit.log_event(
                db=db,
                approval_id=item.id,
                user_id=user_id,
                event_type="EXPIRED",
                old_status="pending",
                new_status="expired",
            )
        if expired_items:
            db.commit()

        query = db.query(Approval).filter(
            Approval.user_id == user_id,
            Approval.workspace_id == workspace_id,
            Approval.status == "pending",
            Approval.expires_at > now,
        )

        total = query.count()
        items = query.order_by(Approval.created_at.desc()).offset(skip).limit(limit).all()
        return items, total

    def approve(self, db: Session, approval_id: int, user_id: int, workspace_id: str) -> Approval:
        """
        Transition status: PENDING -> APPROVED.
        Atomic check enforces pending status & non-expired.
        """
        approval = self.get_approval(db, approval_id, user_id, workspace_id)
        if approval.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve record in '{approval.status}' state",
            )

        now = datetime.now(timezone.utc)
        if approval.expires_at <= now:
            approval.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot approve expired approval record",
            )

        old_status = approval.status
        approval.status = "approved"
        approval.approved_at = now
        approval.updated_at = now

        db.commit()
        db.refresh(approval)

        approval_audit.log_event(
            db=db,
            approval_id=approval.id,
            user_id=user_id,
            event_type="APPROVED",
            old_status=old_status,
            new_status="approved",
        )

        event_publisher.publish(Event(
            event_type=EventType.APPROVAL_GRANTED,
            owner_id=str(user_id),
            payload={"approval_id": approval.id, "action_type": approval.action_type},
        ))

        return approval

    def edit(self, db: Session, approval_id: int, user_id: int, workspace_id: str, data: ApprovalEdit) -> Approval:
        """
        Updates edited_payload. Preserves status as 'pending' so user must review and approve explicitly.
        """
        approval = self.get_approval(db, approval_id, user_id, workspace_id)
        if approval.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot edit approval in '{approval.status}' state",
            )

        now = datetime.now(timezone.utc)
        if approval.expires_at <= now:
            approval.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot edit expired approval record",
            )

        approval.edited_payload = data.edited_payload
        approval.updated_at = now

        db.commit()
        db.refresh(approval)

        approval_audit.log_event(
            db=db,
            approval_id=approval.id,
            user_id=user_id,
            event_type="EDITED",
            old_status="pending",
            new_status="pending",
            metadata_json={"edited_keys": list(data.edited_payload.keys())},
        )

        return approval

    def reject(self, db: Session, approval_id: int, user_id: int, workspace_id: str, data: Optional[ApprovalReject] = None) -> Approval:
        """
        Transition status: PENDING -> REJECTED.
        """
        approval = self.get_approval(db, approval_id, user_id, workspace_id)
        if approval.status not in ("pending", "approved"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject approval in '{approval.status}' state",
            )

        now = datetime.now(timezone.utc)
        old_status = approval.status
        approval.status = "rejected"
        approval.rejected_at = now
        approval.updated_at = now

        db.commit()
        db.refresh(approval)

        reason = data.reason if data else None
        approval_audit.log_event(
            db=db,
            approval_id=approval.id,
            user_id=user_id,
            event_type="REJECTED",
            old_status=old_status,
            new_status="rejected",
            metadata_json={"reason": reason} if reason else None,
        )

        event_publisher.publish(Event(
            event_type=EventType.APPROVAL_REJECTED,
            owner_id=str(user_id),
            payload={"approval_id": approval.id, "action_type": approval.action_type, "reason": reason},
        ))

        return approval

    def validate_approval_for_execution(
        self,
        db: Session,
        approval_id: int,
        user_id: int,
        workspace_id: str,
        expected_action_type: str,
    ) -> Approval:
        """
        Verifies an approval record is valid, approved, unexpired, and matches action_type.
        Does NOT alter state.
        """
        approval = (
            db.query(Approval)
            .filter(
                Approval.id == approval_id,
                Approval.user_id == user_id,
                Approval.workspace_id == workspace_id,
            )
            .first()
        )

        if not approval:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Approved approval #{approval_id} is required before executing this operation",
            )

        if approval.action_type != expected_action_type:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Approval #{approval_id} is for action '{approval.action_type}', expected '{expected_action_type}'",
            )

        if approval.status != "approved":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Approval #{approval_id} status is '{approval.status}', expected 'approved'",
            )

        now = datetime.now(timezone.utc)
        if approval.expires_at <= now:
            approval.status = "expired"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Approval #{approval_id} has expired",
            )

        return approval

    def begin_execution(
        self,
        db: Session,
        approval_id: int,
        user_id: int,
        workspace_id: str,
        expected_action_type: str,
    ) -> Dict[str, Any]:
        """
        Atomic claim: APPROVED -> EXECUTING.
        Uses optimistic database row update lock. Returns effective_payload to execute.
        Raises 403 if claim fails or already consumed.
        """
        approval = self.validate_approval_for_execution(
            db=db,
            approval_id=approval_id,
            user_id=user_id,
            workspace_id=workspace_id,
            expected_action_type=expected_action_type,
        )

        now = datetime.now(timezone.utc)
        
        # Atomic claim transition: approved -> executing
        result = db.query(Approval).filter(
            Approval.id == approval_id,
            Approval.user_id == user_id,
            Approval.workspace_id == workspace_id,
            Approval.status == "approved",
            Approval.expires_at > now,
        ).update(
            {"status": "executing", "updated_at": now},
            synchronize_session=False,
        )

        db.commit()

        if result != 1:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Approval #{approval_id} already consumed, executing, or invalid",
            )

        db.refresh(approval)

        approval_audit.log_event(
            db=db,
            approval_id=approval.id,
            user_id=user_id,
            event_type="EXECUTION_STARTED",
            old_status="approved",
            new_status="executing",
        )

        effective_payload = approval.edited_payload if approval.edited_payload is not None else approval.payload
        return effective_payload

    def complete_execution(self, db: Session, approval_id: int, user_id: int) -> Approval:
        """
        Transition status: EXECUTING -> COMPLETED.
        """
        approval = db.query(Approval).filter(Approval.id == approval_id).first()
        if not approval:
            raise HTTPException(status_code=status.HTTP_444_RESPONSE, detail="Approval not found")

        now = datetime.now(timezone.utc)
        old_status = approval.status
        approval.status = "completed"
        approval.updated_at = now

        db.commit()
        db.refresh(approval)

        approval_audit.log_event(
            db=db,
            approval_id=approval.id,
            user_id=user_id,
            event_type="EXECUTION_COMPLETED",
            old_status=old_status,
            new_status="completed",
        )

        return approval

    def fail_execution(self, db: Session, approval_id: int, user_id: int, error_message: str) -> Approval:
        """
        Transition status: EXECUTING -> FAILED.
        """
        approval = db.query(Approval).filter(Approval.id == approval_id).first()
        if not approval:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approval not found")

        now = datetime.now(timezone.utc)
        old_status = approval.status
        approval.status = "failed"
        approval.updated_at = now

        db.commit()
        db.refresh(approval)

        approval_audit.log_event(
            db=db,
            approval_id=approval.id,
            user_id=user_id,
            event_type="EXECUTION_FAILED",
            old_status=old_status,
            new_status="failed",
            metadata_json={"error": error_message},
        )

        return approval

    def get_approval_events(self, db: Session, approval_id: int, user_id: int, workspace_id: str) -> List[ApprovalEvent]:
        """
        Retrieve full audit log timeline for an approval record.
        """
        # Verifies access ownership
        self.get_approval(db, approval_id, user_id, workspace_id)
        events = (
            db.query(ApprovalEvent)
            .filter(ApprovalEvent.approval_id == approval_id)
            .order_by(ApprovalEvent.created_at.asc())
            .all()
        )
        return events

    def _check_and_update_expiration(self, db: Session, approval: Approval) -> None:
        """
        Internal check to set status to 'expired' if pending and past TTL.
        """
        if approval.status == "pending":
            now = datetime.now(timezone.utc)
            if approval.expires_at <= now:
                approval.status = "expired"
                db.commit()
                approval_audit.log_event(
                    db=db,
                    approval_id=approval.id,
                    user_id=approval.user_id,
                    event_type="EXPIRED",
                    old_status="pending",
                    new_status="expired",
                )

    def to_response_dto(self, approval: Approval) -> ApprovalResponse:
        """
        Convert SQLAlchemy model to Pydantic DTO with effective_payload resolution.
        """
        effective = approval.edited_payload if approval.edited_payload is not None else approval.payload
        return ApprovalResponse(
            id=approval.id,
            user_id=approval.user_id,
            workspace_id=approval.workspace_id,
            execution_id=approval.execution_id,
            action_type=approval.action_type,
            status=approval.status,
            title=approval.title,
            description=approval.description,
            payload=approval.payload,
            edited_payload=approval.edited_payload,
            effective_payload=effective,
            risk_level=approval.risk_level,
            expires_at=approval.expires_at,
            approved_at=approval.approved_at,
            rejected_at=approval.rejected_at,
            created_at=approval.created_at,
            updated_at=approval.updated_at,
        )


approval_service = ApprovalService()
