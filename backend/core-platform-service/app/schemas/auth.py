from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

# bcrypt truncates past 72 bytes, so that is the hard ceiling rather than an
# arbitrary limit.
PASSWORD_MIN_LENGTH = 12
PASSWORD_MAX_LENGTH = 72


class SignupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr = Field(..., max_length=255)
    password: str = Field(
        ...,
        min_length=PASSWORD_MIN_LENGTH,
        max_length=PASSWORD_MAX_LENGTH,
    )


class LoginRequest(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    # No min_length here: rejecting a short password at validation time would
    # tell an attacker their guess was too short instead of simply wrong.
    password: str = Field(..., max_length=PASSWORD_MAX_LENGTH)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_at: Optional[datetime] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1, max_length=4096)


class LogoutRequest(BaseModel):
    """Refresh token is optional; omitting it revokes every active session."""

    refresh_token: Optional[str] = Field(default=None, max_length=4096)

