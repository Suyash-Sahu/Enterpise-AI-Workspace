"""
Workspace dashboard aggregation.

This module used to return a fixed payload: 148 Drive files, 12 Gmail messages,
4 unread, two invented filenames, two invented emails and the address
`alex.dev@enterprise.ai`. None of it came from the signed-in user's account, so
the dashboard looked identical whether Google was connected, disconnected, or
failing. Every figure below is now read from the caller's own Google grant, and
a section that cannot be read reports itself as unavailable rather than
inventing a plausible number.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Optional, TypeVar

from sqlalchemy.orm import Session

from app.connectors.google.drive import GoogleDriveClient
from app.connectors.google.exceptions import GoogleNotConnectedError
from app.connectors.google.gmail import GmailClient
from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.services.google_connector_service import fetch_message_details
from app.services.token_service import TokenService

logger = logging.getLogger(__name__)

T = TypeVar("T")

# The dashboard shows a preview, not the mailbox or the whole Drive. Each of
# these costs Google API calls on every dashboard load, so they stay small.
DRIVE_PREVIEW_LIMIT = 5
GMAIL_PREVIEW_LIMIT = 5

# Every Google call below is a network round trip and none depends on another,
# so they overlap. Run sequentially through the service layer they took ~12s;
# the message previews alone were one list call plus one detail call each.
_MAX_PARALLEL_GOOGLE_CALLS = 8


def _attempt(section: str, unavailable: list[str], fn: Callable[[], T], default: T) -> T:
    """
    Run one dashboard section, recording failure instead of inventing a value.

    A section that cannot be read reports itself as unavailable so the UI can
    say so — the old code returned a fixed number here and the dashboard looked
    identical whether the call succeeded or not.
    """
    try:
        return fn()
    except Exception:
        logger.exception("Dashboard section %r failed", section)
        if section not in unavailable:
            unavailable.append(section)
        return default


class WorkspaceService:

    @staticmethod
    def _active_grant(db: Session, user_id: int) -> Optional[OAuthToken]:
        return (
            db.query(OAuthToken)
            .filter(
                OAuthToken.user_id == user_id,
                OAuthToken.is_active.is_(True),
            )
            .order_by(OAuthToken.id.desc())
            .first()
        )

    @staticmethod
    def get_dashboard(db: Session, user_id: int) -> dict[str, Any]:
        user = db.get(User, user_id)
        grant = WorkspaceService._active_grant(db, user_id)
        connected = grant is not None

        # Identity is the connected Google mailbox when there is one, and the
        # workspace account otherwise — never a placeholder.
        google_email = grant.google_email if grant else None
        email = google_email or (user.email if user else None)
        name = getattr(user, "name", None) or (
            email.split("@")[0].capitalize() if email else "User"
        )

        drive_recent: list[dict[str, Any]] = []
        gmail_latest: list[dict[str, Any]] = []
        gmail_total: Optional[int] = None
        gmail_unread: Optional[int] = None

        # Sections that failed to load, so the UI can say "unavailable"
        # instead of showing a zero that reads as "you have nothing".
        unavailable: list[str] = []

        if connected:
            try:
                # Resolved once, refreshing if near expiry. Every call below is
                # then pure HTTP against Google with no database access, which
                # is what makes it safe to run them on a thread pool.
                access_token = TokenService.get_google_token(db, user_id=user_id)
            except GoogleNotConnectedError:
                access_token = None
                connected = False
            except Exception:
                logger.exception("Dashboard could not resolve a Google access token")
                access_token = None
                unavailable.extend(["drive", "gmail"])

            if access_token:
                gmail = GmailClient(access_token)
                drive = GoogleDriveClient(access_token)

                with ThreadPoolExecutor(
                    max_workers=_MAX_PARALLEL_GOOGLE_CALLS
                ) as pool:
                    drive_future = pool.submit(
                        _attempt,
                        "drive",
                        unavailable,
                        lambda: drive.recent_files(DRIVE_PREVIEW_LIMIT),
                        [],
                    )
                    profile_future = pool.submit(
                        _attempt, "gmail", unavailable, gmail.get_profile, {}
                    )
                    unread_future = pool.submit(
                        _attempt,
                        "gmail",
                        unavailable,
                        lambda: gmail.get_label("UNREAD"),
                        {},
                    )
                    ids_future = pool.submit(
                        _attempt,
                        "gmail",
                        unavailable,
                        lambda: gmail.list_messages(GMAIL_PREVIEW_LIMIT),
                        [],
                    )

                    # Message bodies need one call each, and the ids they need
                    # come from a call of their own. Fan them out the moment
                    # the ids land — blocking on Drive first would put this
                    # second hop behind an unrelated request. fetch_message_details
                    # gives each worker thread its own client, because the
                    # client owns a requests.Session.
                    gmail_latest = _attempt(
                        "gmail",
                        unavailable,
                        lambda: fetch_message_details(access_token, ids_future.result() or []),
                        [],
                    )

                    drive_recent = drive_future.result()
                    gmail_total = (profile_future.result() or {}).get("messagesTotal")
                    gmail_unread = (unread_future.result() or {}).get("messagesUnread")

        return {
            "user": {
                "name": name,
                "email": email,
                "provider": "Google" if google_email else "Local",
            },
            "drive": {
                # The number actually retrieved. Drive has no cheap total, and
                # the previous fixed 148 was not one.
                "count": len(drive_recent),
                "recent": drive_recent,
            },
            "gmail": {
                # Real mailbox totals from the Gmail profile and UNREAD label.
                "count": gmail_total if gmail_total is not None else len(gmail_latest),
                "unread": gmail_unread if gmail_unread is not None else 0,
                "latest": gmail_latest,
            },
            "ai": {
                # NOTE: still static. These describe configured models, not a
                # live health check — nothing here probes the model runtimes.
                "local_model": "qwen2.5:3b-instruct",
                "cloud_model": "google/gemma-4-26b-a4b-it:free",
                "local_status": "unknown",
                "cloud_status": "unknown",
            },
            "workspace": {
                "connected": connected,
                "last_sync": datetime.now(timezone.utc).isoformat(),
                # Additive field: names the sections whose data could not be
                # loaded this request.
                "unavailable": unavailable,
            },
            "capabilities": {
                "drive": connected,
                "gmail": connected,
                "document_ai": True,
                "writer": True,
                "chat": True,
                "rag": True,
                "calendar": False,
            },
        }

    @staticmethod
    def summary(db: Session, user_id: int) -> dict[str, Any]:
        # Previously called get_dashboard(db) with no user_id, so every request
        # to /workspace/summary raised TypeError and returned a 500.
        return WorkspaceService.get_dashboard(db=db, user_id=user_id)
