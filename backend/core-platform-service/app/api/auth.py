"""
Authentication routes.

This service is the only thing that establishes, renews or ends a session.
It owns the Google sign-in round trip end to end and sets the session cookies
itself; the Next app no longer mints cookies, holds tokens, or knows how to
verify an identity. That leaves exactly one identity system.

Every response that creates a session attaches the cookies, and the one that
ends a session clears them. Tokens are still returned in the JSON body for
non-browser callers (scripts, the test suite); the browser never reads them,
because the sign-in path is a redirect and the cookies are httpOnly.
"""

import logging
from typing import Optional
from urllib.parse import urlencode

import requests
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.connectors.google.constants import AUTH_URL, IDENTITY_SCOPES, TOKEN_URL
from app.connectors.google.pkce import (
    generate_code_challenge,
    generate_code_verifier,
    generate_state,
)
from app.connectors.google.userinfo import get_google_user
from app.core.config import settings
from app.core.cookies import clear_session_cookies, set_session_cookies
from app.core.dependencies import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.oauth_state import PURPOSE_CONNECT, PURPOSE_SIGNIN
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshTokenRequest,
    SignupRequest,
    TokenResponse,
)
from app.schemas.user import UserResponse
from app.services.auth_service import (
    AuthError,
    login_or_register_google_user,
    login_user,
    logout_user,
    refresh_access_token,
    signup_user,
)
from app.services.oauth_service import (
    consume_oauth_state,
    purge_expired_oauth_states,
    save_oauth_state,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


def _refresh_token_from(request: Request, supplied: Optional[str]) -> Optional[str]:
    """
    The refresh token, from the request body or the httpOnly cookie.

    Browsers send the cookie and never have the value in script. API clients
    send it in the body. Either is the same token, checked the same way.
    """
    if supplied:
        return supplied

    return request.cookies.get(settings.REFRESH_COOKIE_NAME)


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit(settings.RATE_LIMIT_SIGNUP)
def signup(
    request: Request,
    payload: SignupRequest,
    db: Session = Depends(get_db),
):
    try:
        return signup_user(db, payload)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    db: Session = Depends(get_db),
):
    try:
        tokens = login_user(db, payload)
    except AuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    set_session_cookies(response, tokens)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_REFRESH)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    payload: Optional[RefreshTokenRequest] = None,
):
    def session_over(detail: str) -> JSONResponse:
        # Built explicitly rather than raised: an HTTPException discards the
        # injected Response, so cookies cleared on it would never reach the
        # browser and a dead pair would be retried on every request.
        failure = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": detail},
        )
        clear_session_cookies(failure)
        return failure

    refresh_token = _refresh_token_from(
        request, payload.refresh_token if payload else None
    )

    if not refresh_token:
        return session_over("Invalid refresh token")

    try:
        tokens = refresh_access_token(db, refresh_token)
    except AuthError as e:
        return session_over(str(e))

    # Rotation issues a new refresh token, so the cookie must be replaced.
    set_session_cookies(response, tokens)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    payload: Optional[LogoutRequest] = None,
):
    """Revoke server-side session state so the refresh token stops working."""
    refresh_token = _refresh_token_from(
        request, payload.refresh_token if payload else None
    )

    logout_user(db, refresh_token, current_user)

    # Clear regardless: the server-side session is gone either way, and a
    # cookie left behind would keep failing every request.
    clear_session_cookies(response)
    return None


# =====================================================
# GOOGLE SIGN-IN (identity only)
# =====================================================


def _signin_failed(reason: str) -> RedirectResponse:
    frontend = settings.FRONTEND_URL.rstrip("/")
    return RedirectResponse(url=f"{frontend}/login?error={reason}")


def _verified_google_claims(token_data: dict) -> Optional[dict]:
    """
    Verify the ID token Google returned with the code exchange.

    This checks the signature against Google's published keys, the issuer, the
    expiry, and — the part that matters most — that the audience is *our*
    client ID. A token minted for some other application is rejected, so an
    attacker cannot present a valid-but-foreign Google token and be signed in.

    Returns the claims, or None when there is no usable ID token; the caller
    falls back to the userinfo endpoint in that case.
    """
    raw = token_data.get("id_token")

    if not raw:
        return None

    if not settings.GOOGLE_CLIENT_ID:
        return None

    try:
        return google_id_token.verify_oauth2_token(
            raw,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        # Never log the token itself — only why it was refused.
        logger.warning("Google ID token verification failed: %s", exc)
        return None


@router.get("/google/login")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
def google_signin_start(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Begin signing in with Google.

    Identity scopes only — this grants no access to mail or files. Connecting
    Gmail and Drive is a separate, later, explicit consent.
    """
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        logger.error("Google sign-in attempted with no client credentials configured")
        return _signin_failed("auth_not_configured")

    purge_expired_oauth_states(db)

    verifier = generate_code_verifier()
    state = generate_state()

    # No user_id: who this is becomes known only when Google answers.
    save_oauth_state(
        db=db,
        state=state,
        verifier=verifier,
        user_id=None,
        purpose=PURPOSE_SIGNIN,
    )

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.google_signin_redirect_uri,
        "response_type": "code",
        "scope": " ".join(IDENTITY_SCOPES),
        "state": state,
        "code_challenge": generate_code_challenge(verifier),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }

    return RedirectResponse(url=AUTH_URL + "?" + urlencode(params))


@router.get("/google/callback")
def google_signin_callback(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Complete a Google sign-in and establish the session.

    Google redirects the browser here with no credentials of its own, so
    identity rests on the single-use, short-lived, purpose-checked state row
    and the PKCE verifier it carries.
    """
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        return _signin_failed("missing_code")

    # Not filtered by purpose: this callback serves both flows so that only
    # one redirect URI has to be registered with Google. The row itself says
    # which flow it belongs to, and it is still single-use either way.
    oauth_state = consume_oauth_state(db, state)

    if oauth_state is None:
        return _signin_failed("invalid_state")

    if oauth_state.purpose == PURPOSE_CONNECT:
        # A Gmail/Drive consent came back here. Hand it to the connector,
        # telling it the redirect URI that actually started the flow.
        from app.api.connectors import complete_google_connect

        return complete_google_connect(
            db=db,
            code=code,
            oauth_state=oauth_state,
            redirect_uri=settings.google_connect_authorization_redirect_uri,
        )

    if oauth_state.purpose != PURPOSE_SIGNIN:
        return _signin_failed("invalid_state")

    try:
        token_response = requests.post(
            TOKEN_URL,
            data={
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": settings.google_signin_redirect_uri,
                "code_verifier": oauth_state.code_verifier,
            },
            timeout=15,
        )
        token_data = token_response.json()
    except requests.RequestException as exc:
        logger.warning("Google sign-in token exchange failed: %s", exc)
        return _signin_failed("token_exchange_failed")

    if "access_token" not in token_data:
        # The upstream body can carry client-secret-adjacent detail: log the
        # error code, never return the payload.
        logger.warning(
            "Google sign-in rejected: %s", token_data.get("error", "unknown_error")
        )
        return _signin_failed("token_exchange_failed")

    # Prefer the ID token: it is verified locally against Google's keys with
    # an explicit audience check, and it saves a network round trip. The
    # userinfo endpoint stays as a fallback so a response without an id_token
    # still signs in rather than failing.
    claims = _verified_google_claims(token_data)

    if claims is not None:
        profile = claims
    else:
        try:
            profile = get_google_user(token_data["access_token"])
        except requests.RequestException as exc:
            logger.warning("Google sign-in userinfo lookup failed: %s", exc)
            return _signin_failed("userinfo_failed")

    email = profile.get("email")
    google_sub = profile.get("sub")

    if not email:
        return _signin_failed("userinfo_failed")

    # An unverified address proves nothing about who is signing in. Google
    # sends this as a real bool in the ID token and sometimes as the string
    # "true" from userinfo, so accept both rather than rejecting a verified
    # account on a type mismatch.
    verified = profile.get("email_verified")

    if verified not in (True, "true", "True"):
        return _signin_failed("email_not_verified")

    logger.info(
        "Google sign-in verified for subject %s (source=%s)",
        google_sub or "unknown",
        "id_token" if claims is not None else "userinfo",
    )

    try:
        tokens = login_or_register_google_user(
            db,
            email=email,
            name=profile.get("name") or email.split("@")[0],
        )
    except AuthError as exc:
        logger.warning("Google sign-in could not establish a user: %s", exc)
        return _signin_failed("signin_failed")

    frontend = settings.FRONTEND_URL.rstrip("/")
    redirect = RedirectResponse(url=f"{frontend}/dashboard")

    # The session is delivered as cookies on the redirect, so no token ever
    # reaches the page as script-readable data.
    set_session_cookies(redirect, tokens)

    return redirect
