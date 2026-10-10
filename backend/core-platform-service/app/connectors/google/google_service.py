from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GoogleService:

    @staticmethod
    def build_service(
        service_name: str,
        version: str,
        access_token: str,
    ):
        """
        Build a Google API service using an already-valid access token.

        Token refresh is handled by TokenService before this method is
        called, so this class never performs refresh operations.
        """

        credentials = Credentials(
            token=access_token,
            token_uri="https://oauth2.googleapis.com/token",
        )

        # Prevent the Google client from attempting automatic refresh.
        credentials.expiry = None

        service = build(
            serviceName=service_name,
            version=version,
            credentials=credentials,
            cache_discovery=False,
        )

        return service