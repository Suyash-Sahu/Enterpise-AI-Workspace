import logging
from datetime import datetime, timedelta, timezone

import requests
from sqlalchemy.orm import Session

from app.connectors.google.encryption import decrypt, encrypt
from app.connectors.google.exceptions import GoogleNotConnectedError
from app.connectors.google.refresh import refresh_google_token
from app.models.oauth_token import OAuthToken

logger = logging.getLogger(__name__)


def _refresh_or_disconnect(
    db: Session,
    token: OAuthToken,
    refresh_token: str,
) -> dict:
    """
    Refresh an access token, treating a dead grant as a disconnection.

    A refresh token stops working when the user revokes access, the client
    secret is rotated, or — for an app still in Google's "Testing" publishing
    status — after seven days. None of those are upstream faults the user can
    retry past, so surfacing them as a 502 asked them to retry forever. The
    grant is marked inactive and reported as "not connected", which is the
    state that actually offers them a reconnect.
    """
    try:
        return refresh_google_token(refresh_token)
    except requests.HTTPError as exc:
        response = exc.response
        error = ""

        if response is not None:
            try:
                error = response.json().get("error", "")
            except ValueError:
                error = ""

        if error != "invalid_grant":
            raise

        # Never log the token, only the verdict.
        logger.info(
            "Google grant for user %s is no longer valid; marking disconnected",
            token.user_id,
        )
        token.is_active = False
        db.commit()

        raise GoogleNotConnectedError(
            "Your Google account access expired or was revoked. "
            "Reconnect it to continue."
        ) from exc


class TokenService:

    @staticmethod
    def get_google_token(
        db: Session,
        user_id: int,
    ) -> str:

        token = (
            db.query(OAuthToken)
            .filter(
                OAuthToken.user_id == user_id,
                OAuthToken.is_active.is_(True),
            )
            .order_by(OAuthToken.id.desc())
            .first()
        )

        if token is None:
            raise GoogleNotConnectedError()

        now = datetime.now(timezone.utc)

        expires_at = token.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        # Refresh token 5 minutes before expiry
        if expires_at <= now + timedelta(minutes=5):

            refresh_token = decrypt(
                token.refresh_token
            )

            refreshed = _refresh_or_disconnect(
                db, token, refresh_token
            )

            token.access_token = encrypt(
                refreshed["access_token"]
            )

            token.expires_at = (
                datetime.now(timezone.utc)
                + timedelta(
                    seconds=refreshed["expires_in"]
                )
            )

            token.token_type = refreshed.get(
                "token_type",
                "Bearer",
            )

            db.commit()
            db.refresh(token)

        return decrypt(
            token.access_token
        )

    @staticmethod
    def force_refresh_google_token(
        db: Session,
        user_id: int,
    ) -> str:

        token = (
            db.query(OAuthToken)
            .filter(
                OAuthToken.user_id == user_id,
                OAuthToken.is_active.is_(True),
            )
            .order_by(OAuthToken.id.desc())
            .first()
        )

        if token is None:
            raise GoogleNotConnectedError()

        refresh_token = decrypt(
            token.refresh_token
        )

        refreshed = _refresh_or_disconnect(
            db, token, refresh_token
        )

        token.access_token = encrypt(
            refreshed["access_token"]
        )

        token.expires_at = (
            datetime.now(timezone.utc)
            + timedelta(
                seconds=refreshed["expires_in"]
            )
        )

        token.token_type = refreshed.get(
            "token_type",
            "Bearer",
        )

        db.commit()
        db.refresh(token)

        return decrypt(
            token.access_token
        )

    @staticmethod
    def get_latest_google_token(
        db: Session,
        user_id: int,
    ) -> OAuthToken:

        token = (
            db.query(OAuthToken)
            .filter(
                OAuthToken.user_id == user_id,
                OAuthToken.is_active.is_(True),
            )
            .order_by(OAuthToken.id.desc())
            .first()
        )

        if token is None:
            raise GoogleNotConnectedError()

        return token