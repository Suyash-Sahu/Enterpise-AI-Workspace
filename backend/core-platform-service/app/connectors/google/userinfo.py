import requests

from app.connectors.google.constants import USERINFO_URL


def get_google_user(access_token: str):
    # Without a timeout a hung call here blocks the OAuth callback, and with
    # it the browser the user is waiting on.
    response = requests.get(
        USERINFO_URL,
        headers={
            "Authorization": f"Bearer {access_token}"
        },
        timeout=15,
    )

    response.raise_for_status()

    return response.json()