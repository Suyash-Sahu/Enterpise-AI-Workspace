import requests

from shared.common.config import ServiceURLs


class ConnectorClient:
    """
    SDK used by all backend services to communicate
    with the Connector Service.
    """

    def __init__(self):
        self.base_url = ServiceURLs.CONNECTOR.rstrip("/")

    # ===========================
    # DRIVE
    # ===========================

    def list_drive_files(self):
        response = requests.get(
            f"{self.base_url}/connectors/google/drive/files"
        )
        response.raise_for_status()
        return response.json()

    def download_file(self, file_id: str):
        response = requests.get(
            f"{self.base_url}/connectors/google/drive/download/{file_id}"
        )
        response.raise_for_status()
        return response.content

    def export_google_doc(self, file_id: str):
        response = requests.get(
            f"{self.base_url}/connectors/google/drive/export/{file_id}"
        )
        response.raise_for_status()
        return response.text

    # ===========================
    # GMAIL
    # ===========================

    def list_gmail_threads(self):
        response = requests.get(
            f"{self.base_url}/connectors/google/gmail/threads"
        )
        response.raise_for_status()
        return response.json()

    def list_gmail_messages(self):
        response = requests.get(
            f"{self.base_url}/connectors/google/gmail/messages"
        )
        response.raise_for_status()
        return response.json()

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
    ):
        response = requests.post(
            f"{self.base_url}/connectors/google/gmail/send",
            json={
                "to": to,
                "subject": subject,
                "body": body,
            },
        )

        response.raise_for_status()

        return response.json()