"""
Meeting service (AMOF-X Phase 7): persists Meeting/MeetingActionItem rows
from a MeetingAgent extraction. Mirrors workgraph_service.py's shape (a
thin class over direct DB queries).
"""
import json
from typing import Optional
from sqlalchemy.orm import Session

from app.models.meeting import Meeting, MeetingActionItem
from app.schemas.meeting import ActionItemResponse, MeetingResponse


class MeetingService:

    @staticmethod
    def create_meeting(
        db: Session,
        owner_id: str,
        transcript_text: str,
        transcript_source: str = "manual_paste",
    ) -> Meeting:
        meeting = Meeting(
            owner_id=owner_id,
            transcript_source=transcript_source,
            transcript_text=transcript_text,
            status="pending",
        )
        db.add(meeting)
        db.commit()
        db.refresh(meeting)
        return meeting

    @staticmethod
    def store_extraction(db: Session, meeting: Meeting, extraction: dict) -> Meeting:
        meeting.summary = extraction.get("summary", "")
        meeting.extraction_json = json.dumps(extraction)
        meeting.status = "processed"
        db.add(meeting)
        db.flush()

        for item in extraction.get("action_items", []):
            db.add(
                MeetingActionItem(
                    meeting_id=meeting.id,
                    description=item.get("description", ""),
                    owner=item.get("owner"),
                    due_date=item.get("due_date"),
                )
            )

        db.commit()
        db.refresh(meeting)
        return meeting

    @staticmethod
    def get_meeting(db: Session, owner_id: str, meeting_id: str) -> Optional[Meeting]:
        return (
            db.query(Meeting)
            .filter(Meeting.id == meeting_id, Meeting.owner_id == owner_id)
            .first()
        )

    @staticmethod
    def get_action_item(db: Session, meeting_id: str, item_id: str) -> Optional[MeetingActionItem]:
        return (
            db.query(MeetingActionItem)
            .filter(MeetingActionItem.id == item_id, MeetingActionItem.meeting_id == meeting_id)
            .first()
        )

    @staticmethod
    def list_action_items(db: Session, meeting_id: str) -> list[MeetingActionItem]:
        return (
            db.query(MeetingActionItem)
            .filter(MeetingActionItem.meeting_id == meeting_id)
            .all()
        )

    @staticmethod
    def list_action_items_for_owner(db: Session, owner_id: str) -> list[MeetingActionItem]:
        """Every action item across all of one owner's meetings -- used by the
        commitment scan, which reasons over an owner's commitments regardless
        of which meeting produced them."""
        return (
            db.query(MeetingActionItem)
            .join(Meeting, MeetingActionItem.meeting_id == Meeting.id)
            .filter(Meeting.owner_id == owner_id)
            .all()
        )

    @staticmethod
    def link_action_item_task(db: Session, item: MeetingActionItem, task_id: str) -> MeetingActionItem:
        item.workgraph_task_id = task_id
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def to_response_dto(db: Session, meeting: Meeting) -> MeetingResponse:
        extraction = json.loads(meeting.extraction_json) if meeting.extraction_json else {}
        items = (
            db.query(MeetingActionItem)
            .filter(MeetingActionItem.meeting_id == meeting.id)
            .all()
        )
        return MeetingResponse(
            id=meeting.id,
            owner_id=meeting.owner_id,
            transcript_source=meeting.transcript_source,
            status=meeting.status,
            summary=meeting.summary,
            decisions=extraction.get("decisions", []),
            risks=extraction.get("risks", []),
            unresolved_questions=extraction.get("unresolved_questions", []),
            action_items=[ActionItemResponse.model_validate(i) for i in items],
            created_at=meeting.created_at,
        )


meeting_service = MeetingService()
