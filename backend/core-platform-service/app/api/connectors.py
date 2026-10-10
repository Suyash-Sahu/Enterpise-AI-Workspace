import logging
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import PlainTextResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.connectors.google.constants import AUTH_URL, SCOPES, TOKEN_URL
from app.connectors.google.encryption import encrypt
from app.connectors.google.exceptions import GoogleNotConnectedError
from app.connectors.google.pkce import (
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)
from app.connectors.google.userinfo import get_google_user
from app.core.config import settings
from app.core.dependencies import get_current_user, get_db
from app.models.oauth_state import PURPOSE_CONNECT
from app.models.oauth_token import OAuthToken
from app.models.user import User
from app.schemas.connector import EmailRequest
from app.services.approval.approval_service import approval_service
from app.services.google_connector_service import GoogleConnectorService
from app.services.oauth_service import (
    consume_oauth_state,
    purge_expired_oauth_states,
    save_oauth_state,
)
from app.utils.response import success_response

logger = logging.getLogger(__name__)

# Every route here reads or writes the caller's Google data, so authentication
# is applied at the router level: a new route cannot be added without it.
router = APIRouter(
    prefix="/connectors/google",
    tags=["Google Connector"],
    dependencies=[Depends(get_current_user)],
)

# Google redirects the browser here with no Authorization header, so this one
# route must stay public. It derives identity from the signed, user-bound,
# short-lived state row instead.
public_router = APIRouter(
    prefix="/connectors/google",
    tags=["Google Connector"],
)


def _connector_error(exc: Exception) -> HTTPException:
    """
    Log the detail, return a generic message.

    "No account connected" is separated from "Google refused the call": the
    first is fixed by the user connecting an account, the second is an upstream
    fault they can do nothing about. Collapsing both into 502 left the UI
    showing a retry for a problem retrying could never solve.
    """
    if isinstance(exc, GoogleNotConnectedError):
        logger.info("Google connector call made with no active grant")
        return HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No Google account is connected. Connect one to continue.",
        )

    logger.exception("Google connector call failed: %s", exc)
    return HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="Google request failed. Try reconnecting your account.",
    )


# =====================================================
# GOOGLE STATUS
# =====================================================


@router.get("/status")
def google_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    token = (
        db.query(OAuthToken)
        .filter(
            OAuthToken.user_id == current_user.id,
            OAuthToken.is_active.is_(True),
        )
        .order_by(OAuthToken.id.desc())
        .first()
    )

    if token:
        expires_str = token.expires_at.isoformat() if token.expires_at else None
        return success_response(
            data={
                "connected": True,
                "email": token.google_email,
                "expires_at": expires_str,
            },
            message="Google connector is active",
        )

    return success_response(
        data={"connected": False},
        message="Google connector is not connected",
    )


# =====================================================
# GOOGLE CONNECT (authorization URL)
# =====================================================


@router.get("/login")
def google_login(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Start connecting the signed-in user's Google account.

    Returns the authorization URL as JSON rather than a 307 so the browser
    can send its bearer token — a plain redirect could not be authenticated,
    which is what previously allowed anyone to bind a Google account to the
    workspace.
    """
    purge_expired_oauth_states(db)

    verifier = generate_code_verifier()
    state = generate_state()

    save_oauth_state(
        db=db,
        state=state,
        verifier=verifier,
        user_id=current_user.id,
    )

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        # Ride the sign-in callback so only one redirect URI has to be
        # registered with Google; the state row's purpose tells that handler
        # this is a connect, not a sign-in.
        "redirect_uri": settings.google_connect_authorization_redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": generate_code_challenge(verifier),
        "code_challenge_method": "S256",
    }

    return success_response(
        data={"authorization_url": AUTH_URL + "?" + urlencode(params)},
        message="Google authorization URL generated",
    )


# =====================================================
# GOOGLE CALLBACK (public — see note above)
# =====================================================


def connect_failed(reason: str) -> RedirectResponse:
    """Errors go back to the UI as a redirect, never as raw upstream JSON."""
    frontend = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(
        url=f"{frontend}/integrations?connected=false&error={reason}"
    )


def complete_google_connect(
    db: Session,
    code: str,
    oauth_state,
    redirect_uri: str,
) -> RedirectResponse:
    """
    Exchange a consent code for Gmail/Drive tokens and store them.

    Split out of the route because the sign-in callback completes this same
    flow: both callbacks are reachable, and the authorization request decides
    which one Google returns to. `redirect_uri` must be the exact value that
    started the flow, or Google refuses the exchange.

    The state row is already consumed by the caller — whoever consumed it owns
    deciding that it was genuine.
    """
    frontend = settings.FRONTEND_URL.rstrip("/")
    fail = connect_failed
    user_id = oauth_state.user_id

    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code_verifier": oauth_state.code_verifier,
            },
            timeout=15,
        )
        token_data = response.json()
    except requests.RequestException as exc:
        logger.warning("Google token exchange failed: %s", exc)
        return fail("token_exchange_failed")

    if "access_token" not in token_data:
        # token_data can carry client_secret-adjacent detail; log, never return.
        logger.warning(
            "Google token exchange rejected: %s",
            token_data.get("error", "unknown_error"),
        )
        return fail("token_exchange_failed")

    try:
        user_info = get_google_user(token_data["access_token"])
    except requests.RequestException as exc:
        logger.warning("Google userinfo lookup failed: %s", exc)
        return fail("userinfo_failed")

    expires_at = datetime.now(timezone.utc) + timedelta(
        seconds=int(token_data.get("expires_in", 3600))
    )

    refresh_token = token_data.get("refresh_token", "")

    # Reconnecting replaces the previous grant rather than stacking another
    # row that every read then has to sort past.
    db.query(OAuthToken).filter(
        OAuthToken.user_id == user_id,
        OAuthToken.is_active.is_(True),
    ).update({OAuthToken.is_active: False}, synchronize_session=False)

    db.add(
        OAuthToken(
            user_id=user_id,
            google_email=user_info["email"],
            access_token=encrypt(token_data["access_token"]),
            refresh_token=encrypt(refresh_token),
            scopes=" ".join(SCOPES),
            expires_at=expires_at,
            token_type=token_data.get("token_type", "Bearer"),
            is_active=True,
        )
    )
    db.commit()

    return RedirectResponse(url=f"{frontend}/integrations?connected=true")


@public_router.get("/oauth/callback")
def google_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Dedicated connector callback.

    Still live, but only used when GOOGLE_REDIRECT_URI is set explicitly.
    By default the connector rides the sign-in callback instead, so that a
    single redirect URI has to be registered with Google.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        return connect_failed("missing_parameters")

    # Single-use: the row is deleted as it is read, so a replayed callback
    # finds nothing.
    oauth_state = consume_oauth_state(db, state, expected_purpose=PURPOSE_CONNECT)

    if oauth_state is None:
        return connect_failed("invalid_state")

    return complete_google_connect(
        db=db,
        code=code,
        oauth_state=oauth_state,
        redirect_uri=settings.google_connector_redirect_uri,
    )


# =====================================================
# GOOGLE DRIVE
# =====================================================


@router.get("/drive/files")
def list_drive_files(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        files = GoogleConnectorService.list_drive_files(
            db=db,
            user_id=current_user.id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"count": len(files), "files": files},
        message="Drive files retrieved successfully",
    )


@router.get("/drive/file/{file_id}")
def get_drive_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return success_response(
            data=GoogleConnectorService.drive_file_details(
                db=db,
                user_id=current_user.id,
                file_id=file_id,
            ),
            message="Drive file details retrieved",
        )
    except Exception as exc:
        raise _connector_error(exc)


@router.get("/drive/download/{file_id}")
def download_drive_file(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        data = GoogleConnectorService.download_drive_file(
            db=db,
            user_id=current_user.id,
            file_id=file_id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"size": len(data)},
        message="Drive file downloaded",
    )


@router.get("/drive/export/{file_id}", response_class=PlainTextResponse)
def export_google_doc(
    file_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return GoogleConnectorService.export_google_doc(
            db=db,
            user_id=current_user.id,
            file_id=file_id,
        )
    except Exception as exc:
        raise _connector_error(exc)


@router.get("/drive/search")
def drive_search(
    q: str = Query(..., min_length=1, max_length=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        files = GoogleConnectorService.search_drive_files(
            db=db,
            user_id=current_user.id,
            query=q,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"count": len(files), "files": files},
        message="Drive search completed",
    )


@router.get("/drive/recent")
def drive_recent(
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        files = GoogleConnectorService.recent_drive_files(
            db=db,
            user_id=current_user.id,
            limit=limit,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"count": len(files), "files": files},
        message="Recent Drive files retrieved",
    )


@router.get("/drive/folders")
def drive_folders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        folders = GoogleConnectorService.drive_folders(
            db=db,
            user_id=current_user.id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"folders": folders},
        message="Drive folders retrieved",
    )


# =====================================================
# GMAIL
# =====================================================


@router.get("/gmail/unread")
def unread_emails(
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    try:
        emails = GoogleConnectorService.unread_messages(
            db=db,
            user_id=current_user.id,
            limit=limit,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"count": len(emails), "emails": emails},
        message="Unread emails retrieved successfully",
        start_time=start_time,
    )


@router.get("/gmail/labels")
def gmail_labels(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    try:
        labels = GoogleConnectorService.list_labels(
            db=db,
            user_id=current_user.id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"labels": labels},
        message="Gmail labels retrieved successfully",
        start_time=start_time,
    )


@router.get("/gmail/profile")
def gmail_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    try:
        profile_data = GoogleConnectorService.get_profile(
            db=db,
            user_id=current_user.id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data=profile_data,
        message="Gmail profile retrieved successfully",
        start_time=start_time,
    )


@router.get("/gmail/threads")
def gmail_threads(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    try:
        threads = GoogleConnectorService.list_gmail_threads(
            db=db,
            user_id=current_user.id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"count": len(threads), "threads": threads},
        message="Gmail threads retrieved successfully",
        start_time=start_time,
    )


@router.get("/gmail/thread/{thread_id}")
def gmail_thread(
    thread_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    try:
        thread = GoogleConnectorService.get_gmail_thread(
            db=db,
            user_id=current_user.id,
            thread_id=thread_id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data=thread,
        message="Gmail thread details retrieved",
        start_time=start_time,
    )


@router.get("/gmail/messages")
def gmail_messages(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    try:
        messages = GoogleConnectorService.list_gmail_messages(
            db=db,
            user_id=current_user.id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"count": len(messages), "messages": messages},
        message="Gmail messages retrieved successfully",
        start_time=start_time,
    )


@router.get("/gmail/message/{message_id}")
def gmail_message(
    message_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    try:
        message = GoogleConnectorService.get_gmail_message(
            db=db,
            user_id=current_user.id,
            message_id=message_id,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data=message,
        message="Gmail message retrieved",
        start_time=start_time,
    )


@router.get("/gmail/search")
def gmail_search(
    q: str = Query(..., min_length=1, max_length=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        results = GoogleConnectorService.search_messages(
            db=db,
            user_id=current_user.id,
            query=q,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data={"count": len(results), "results": results},
        message="Gmail search completed",
    )


@router.post("/gmail/draft")
def create_draft(
    request: EmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    start_time = time.time()

    try:
        result = GoogleConnectorService.create_draft(
            db=db,
            user_id=current_user.id,
            to=request.to,
            subject=request.subject,
            body=request.body,
        )
    except Exception as exc:
        raise _connector_error(exc)

    return success_response(
        data=result,
        message="Draft created successfully",
        start_time=start_time,
    )


@router.post("/gmail/send")
def send_email(
    request: EmailRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send mail via the Gmail API.

    Invariant: requires a valid, unexpired, unconsumed approval record owned by
    the calling user.
    """
    if not request.approval_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="An approved approval record is required before sending email",
        )

    user_id = current_user.id
    workspace_id = f"ws_user_{user_id}"

    try:
        # Atomically claim the approval and resolve the payload that was
        # actually approved — not whatever the request body says.
        effective_payload = approval_service.begin_execution(
            db=db,
            approval_id=request.approval_id,
            user_id=user_id,
            workspace_id=workspace_id,
            expected_action_type="gmail.send",
        )

        to_addr = effective_payload.get("to", request.to)
        if isinstance(to_addr, list):
            to_addr = ", ".join(to_addr)

        result = GoogleConnectorService.send_email(
            db=db,
            user_id=user_id,
            to=to_addr,
            subject=effective_payload.get("subject", request.subject),
            body=effective_payload.get("body", request.body),
        )

        approval_service.complete_execution(
            db=db,
            approval_id=request.approval_id,
            user_id=user_id,
        )

        return success_response(data=result, message="Email sent successfully")

    except HTTPException:
        raise
    except Exception as exc:
        try:
            approval_service.fail_execution(
                db=db,
                approval_id=request.approval_id,
                user_id=user_id,
                error_message=str(exc),
            )
        except Exception:
            logger.exception("Failed to record approval execution failure")

        raise _connector_error(exc)
