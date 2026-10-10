import requests

from app.connectors.google.constants import TOKEN_URL
from app.core.config import settings


def refresh_google_token(refresh_token: str):
    response = requests.post(
        TOKEN_URL,
        data={
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
    )

    response.raise_for_status()

    return response.json()