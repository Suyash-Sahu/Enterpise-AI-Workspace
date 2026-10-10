from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class EmailRequest(BaseModel):
    """
    Outbound mail payload for the Gmail connector.

    For /gmail/send this is only a fallback: the approved approval record is
    the authority on what actually gets sent.
    """

    to: EmailStr = Field(..., max_length=320)
    subject: str = Field(..., min_length=1, max_length=998)
    body: str = Field(..., max_length=100_000)
    approval_id: Optional[int] = Field(default=None, ge=1)
