import base64
from email.mime.text import MIMEText

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class GmailClient:

    BASE_URL = "https://gmail.googleapis.com/gmail/v1/users/me"

    # Reading an inbox page costs one list call plus one call per message, so a
    # fresh TCP+TLS handshake per request meant ~21 handshakes for a single
    # page — slow enough to look hung, and Google reset the connection often
    # enough that /gmail/unread failed outright. A Session keeps the connection
    # alive across all of them.
    TIMEOUT_SECONDS = 20

    # Retries cover transient resets and Google's rate limiting. urllib3's
    # default allowed_methods is deliberately kept: it excludes POST, so
    # sending mail and creating drafts are never retried and cannot be
    # duplicated by a retry.
    _RETRY_POLICY = Retry(
        total=3,
        connect=3,
        read=2,
        backoff_factor=0.5,
        status_forcelist=(429, 500, 502, 503, 504),
        raise_on_status=False,
    )

    def __init__(
        self,
        access_token: str,
        pool_size: int = 10,
    ):

        self.access_token = access_token

        self._session = requests.Session()

        adapter = HTTPAdapter(
            max_retries=self._RETRY_POLICY,
            pool_connections=pool_size,
            pool_maxsize=pool_size,
        )
        self._session.mount("https://", adapter)

    # =====================================================
    # INTERNAL REQUEST
    # =====================================================

    def _request(
        self,
        method: str,
        endpoint: str,
        **kwargs,
    ):

        headers = kwargs.pop(
            "headers",
            {},
        )

        headers["Authorization"] = (
            f"Bearer {self.access_token}"
        )

        kwargs.setdefault("timeout", self.TIMEOUT_SECONDS)

        response = self._session.request(
            method=method,
            url=f"{self.BASE_URL}{endpoint}",
            headers=headers,
            **kwargs,
        )

        response.raise_for_status()

        if response.text.strip():

            return response.json()

        return {}

    # =====================================================
    # MESSAGE LIST
    # =====================================================

    def list_messages(
        self,
        max_results: int = 20,
    ):

        result = self._request(
            "GET",
            "/messages",
            params={
                "maxResults": max_results,
            },
        )

        return result.get(
            "messages",
            [],
        )

    # =====================================================
    # SEARCH
    # =====================================================

    def search_messages(
        self,
        query: str,
        max_results: int = 20,
    ):

        result = self._request(
            "GET",
            "/messages",
            params={
                "q": query,
                "maxResults": max_results,
            },
        )

        return result.get(
            "messages",
            [],
        )

    # =====================================================
    # GET MESSAGE
    # =====================================================

    def get_message(
        self,
        message_id: str,
    ):

        return self._request(
            "GET",
            f"/messages/{message_id}",
            params={
                "format": "full",
            },
        )

    # =====================================================
    # BASE64 DECODER
    # =====================================================

    def _decode_base64(
        self,
        data: str,
    ) -> str:

        if not data:
            return ""

        padding = "=" * (-len(data) % 4)

        return base64.urlsafe_b64decode(
            data + padding
        ).decode(
            "utf-8",
            errors="ignore",
        )

    # =====================================================
    # EMAIL BODY
    # =====================================================

    def get_email_body(
        self,
        message,
    ) -> str:

        payload = message.get(
            "payload",
            {},
        )

        # Multipart email
        if "parts" in payload:

            for part in payload["parts"]:

                mime = part.get(
                    "mimeType",
                    "",
                )

                if mime == "text/plain":

                    data = (
                        part.get(
                            "body",
                            {},
                        ).get("data")
                    )

                    if data:

                        return self._decode_base64(
                            data
                        )

        # Single part email
        body = payload.get(
            "body",
            {},
        )

        data = body.get("data")

        if data:

            return self._decode_base64(
                data
            )

        return ""

    # =====================================================
    # MESSAGE DETAILS
    # =====================================================

    def get_message_details(
        self,
        message_id: str,
    ) -> dict:

        message = self.get_message(
            message_id
        )

        headers = (
            message.get(
                "payload",
                {},
            ).get(
                "headers",
                [],
            )
        )

        subject = ""
        sender = ""
        receiver = ""
        date = ""

        for header in headers:

            name = header.get(
                "name",
                "",
            )

            value = header.get(
                "value",
                "",
            )

            if name == "Subject":
                subject = value

            elif name == "From":
                sender = value

            elif name == "To":
                receiver = value

            elif name == "Date":
                date = value

        return {
            "id": message.get("id"),
            "threadId": message.get("threadId"),
            "subject": subject,
            "from": sender,
            "to": receiver,
            "date": date,
            "snippet": message.get(
                "snippet",
                "",
            ),
            "body": self.get_email_body(
                message
            ),
        }

    # =====================================================
    # LABELS
    # =====================================================

    def list_labels(
        self,
    ):

        result = self._request(
            "GET",
            "/labels",
        )

        return result.get(
            "labels",
            [],
        )

    # =====================================================
    # UNREAD EMAILS
    # =====================================================

    def unread_messages(
        self,
        max_results: int = 20,
    ):

        result = self._request(
            "GET",
            "/messages",
            params={
                "labelIds": "UNREAD",
                "maxResults": max_results,
            },
        )

        return result.get(
            "messages",
            [],
        )
    # =====================================================
    # THREADS
    # =====================================================

    def list_threads(
        self,
        max_results: int = 20,
    ):

        result = self._request(
            "GET",
            "/threads",
            params={
                "maxResults": max_results,
            },
        )

        return result.get(
            "threads",
            [],
        )

    def get_thread(
        self,
        thread_id: str,
    ):

        return self._request(
            "GET",
            f"/threads/{thread_id}",
        )

    # =====================================================
    # SEND EMAIL
    # =====================================================

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
    ):

        message = MIMEText(body)

        message["To"] = to
        message["Subject"] = subject

        raw = (
            base64.urlsafe_b64encode(
                message.as_bytes()
            )
            .decode()
            .rstrip("=")
        )

        return self._request(
            "POST",
            "/messages/send",
            json={
                "raw": raw,
            },
        )

    # =====================================================
    # CREATE DRAFT
    # =====================================================

    def create_draft(
        self,
        to: str,
        subject: str,
        body: str,
    ):

        message = MIMEText(body)

        message["To"] = to
        message["Subject"] = subject

        raw = (
            base64.urlsafe_b64encode(
                message.as_bytes()
            )
            .decode()
            .rstrip("=")
        )

        return self._request(
            "POST",
            "/drafts",
            json={
                "message": {
                    "raw": raw,
                }
            },
        )

    # =====================================================
    # PROFILE
    # =====================================================

    def get_profile(
        self,
    ):

        return self._request(
            "GET",
            "/profile",
        )

    def get_label(
        self,
        label_id: str,
    ):
        """
        A single label, including its exact message counts.

        `list_labels` returns names only, so counting unread meant paging
        through message ids and reporting the page size as the total.
        """

        return self._request(
            "GET",
            f"/labels/{label_id}",
        )