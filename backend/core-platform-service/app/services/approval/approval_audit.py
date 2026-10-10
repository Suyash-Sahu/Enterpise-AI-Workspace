"""
Project 8 — Approval Audit Logger
Appends structured lifecycle events to the approval_events database table.
"""

from typing import Optional, Any
from sqlalchemy.orm import Session
from app.models.approval_event import ApprovalEvent


class ApprovalAuditLogger:
    @staticmethod
    def log_event(
        db: Session,
        approval_id: int,
        user_id: int,
        event_type: str,
        new_status: str,
        old_status: Optional[str] = None,
        metadata_json: Optional[dict[str, Any]] = None,
    ) -> ApprovalEvent:
        event = ApprovalEvent(
            approval_id=approval_id,
            user_id=user_id,
            event_type=event_type,
            old_status=old_status,
            new_status=new_status,
            metadata_json=metadata_json,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        return event


approval_audit = ApprovalAuditLogger()
