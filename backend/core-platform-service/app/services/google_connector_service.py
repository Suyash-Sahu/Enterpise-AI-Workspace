import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Optional

from sqlalchemy.orm import Session
import requests

from googleapiclient.errors import HttpError

from app.connectors.google.drive import GoogleDriveClient
from app.connectors.google.gmail import GmailClient
from app.services.token_service import TokenService

# Gmail returns message ids, and the body of each one costs a separate call.
# Run sequentially that was ~21 round trips for a single inbox page, which
# took over 30 seconds and read as a hang.
_MESSAGE_DETAIL_WORKERS = 8

# requests.Session is not documented as thread-safe, so each worker thread
# gets its own client rather than sharing one across the pool.
_thread_local = threading.local()


def _thread_gmail_client(access_token: str) -> GmailClient:
    client = getattr(_thread_local, "gmail_client", None)

    if client is None or client.access_token != access_token:
        client = GmailClient(access_token)
        _thread_local.gmail_client = client

    return client


def fetch_message_details(access_token: str, messages: Any) -> list:
    """Fetch each message body concurrently, preserving the listed order."""
    if isinstance(messages, dict):
        messages = messages.get("messages", [])
    if not isinstance(messages, list):
        return []

    # If messages already have subject and snippet (e.g. mocked or full objects), return them
    if messages and isinstance(messages[0], dict) and ("subject" in messages[0] or "snippet" in messages[0]) and "payload" not in messages[0]:
        return messages

    message_ids = [m["id"] for m in messages if isinstance(m, dict) and m.get("id")]

    if not message_ids:
        return []

    def fetch(message_id: str):
        try:
            return _thread_gmail_client(access_token).get_message_details(message_id)
        except Exception:
            return {"id": message_id, "subject": "(Email details unavailable)", "snippet": ""}

    with ThreadPoolExecutor(
        max_workers=min(_MESSAGE_DETAIL_WORKERS, len(message_ids))
    ) as pool:
        return list(pool.map(fetch, message_ids))


class GoogleConnectorService:

    # =====================================================
    # INTERNAL
    # =====================================================

    @staticmethod
    def _gmail(
        db: Session,
        user_id: int,
    ):

        token = TokenService.get_google_token(db, user_id=user_id)

        return GmailClient(token)

    @staticmethod
    def _drive(
        db: Session,
        user_id: int,
    ):

        token = TokenService.get_google_token(db, user_id=user_id)

        return GoogleDriveClient(token)

    # =====================================================
    # DRIVE
    # =====================================================

    @staticmethod
    def list_drive_files(
        db: Session,
        user_id: int,
    ):

        try:

            drive = GoogleConnectorService._drive(db, user_id)

            return drive.list_files()

        except HttpError as e:

            if e.resp.status == 401:

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                drive = GoogleDriveClient(token)

                return drive.list_files()

            raise

    @staticmethod
    def recent_drive_files(
        db: Session,
        user_id: int,
        limit: int = 10,
    ):

        try:

            drive = GoogleConnectorService._drive(db, user_id)

            return drive.recent_files(limit)

        except HttpError as e:

            if e.resp.status == 401:

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                drive = GoogleDriveClient(token)

                return drive.recent_files(limit)

            raise

    @staticmethod
    def drive_folders(
        db: Session,
        user_id: int,
    ):

        try:

            drive = GoogleConnectorService._drive(db, user_id)

            return drive.folders()

        except HttpError as e:

            if e.resp.status == 401:

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                drive = GoogleDriveClient(token)

                return drive.folders()

            raise

    @staticmethod
    def drive_file_details(
        db: Session,
        user_id: int,
        file_id: str,
    ):

        try:

            drive = GoogleConnectorService._drive(db, user_id)

            return drive.file_details(file_id)

        except HttpError as e:

            if e.resp.status == 401:

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                drive = GoogleDriveClient(token)

                return drive.file_details(file_id)

            raise

    @staticmethod
    def download_drive_file(
        db: Session,
        user_id: int,
        file_id: str,
    ):

        try:

            drive = GoogleConnectorService._drive(db, user_id)

            return drive.download_file(file_id)

        except HttpError as e:

            if e.resp.status == 401:

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                drive = GoogleDriveClient(token)

                return drive.download_file(file_id)

            raise

    

    @staticmethod
    def search_drive_files(
        db: Session,
        user_id: int,
        query: str,
    ):

        try:

            drive = GoogleConnectorService._drive(db, user_id)

            return drive.search_files(query)

        except HttpError as e:

            if e.resp.status == 401:

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                drive = GoogleDriveClient(token)

                return drive.search_files(query)

            raise

    @staticmethod
    def export_google_doc(
        db: Session,
        user_id: int,
        file_id: str,
    ):

        try:

            drive = GoogleConnectorService._drive(db, user_id)

            return drive.export_google_doc(file_id)

        except HttpError as e:

            if e.resp.status == 401:

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                drive = GoogleDriveClient(token)

                return drive.export_google_doc(file_id)

            raise

    # =====================================================
    # GMAIL
    # =====================================================

    @staticmethod
    def list_message_details(
        db: Session,
        user_id: int,
        limit: int = 10,
    ):

        token = TokenService.get_google_token(db, user_id=user_id)

        try:

            messages = GmailClient(token).list_messages(limit)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                messages = GmailClient(token).list_messages(limit)

            else:

                raise

        return fetch_message_details(token, messages)

    @staticmethod
    def search_messages(
        db: Session,
        user_id: int,
        query: str,
        limit: int = 20,
    ):

        token = TokenService.get_google_token(db, user_id=user_id)

        try:

            messages = GmailClient(token).search_messages(query, limit)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                messages = GmailClient(token).search_messages(query, limit)

            else:

                raise

        return fetch_message_details(token, messages)

    @staticmethod
    def unread_messages(
        db: Session,
        user_id: int,
        limit: int = 50,
        page_token: Optional[str] = None,
    ):
        token = TokenService.get_google_token(db, user_id=user_id)
        try:
            raw = GmailClient(token).unread_messages(limit, page_token=page_token)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                token = TokenService.force_refresh_google_token(db, user_id=user_id)
                raw = GmailClient(token).unread_messages(limit, page_token=page_token)
            else:
                raise

        if isinstance(raw, list):
            return raw
        items = raw.get("messages", []) if isinstance(raw, dict) else []
        return fetch_message_details(token, items)

    @staticmethod
    def get_unread_summary(
        db: Session,
        user_id: int,
        limit: int = 50,
        page_token: Optional[str] = None,
    ) -> dict:
        """
        Fetch unread emails with pagination metadata and accurate unread counts.
        """
        token = TokenService.get_google_token(db, user_id=user_id)
        gmail = GmailClient(token)
        try:
            raw = gmail.unread_messages(max_results=limit, page_token=page_token)
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 401:
                token = TokenService.force_refresh_google_token(db, user_id=user_id)
                gmail = GmailClient(token)
                raw = gmail.unread_messages(max_results=limit, page_token=page_token)
            else:
                raise

        if isinstance(raw, list):
            items = raw
            next_page_token = None
            total_estimate = len(raw)
        else:
            items = raw.get("messages", []) if isinstance(raw, dict) else []
            next_page_token = raw.get("nextPageToken") if isinstance(raw, dict) else None
            total_estimate = raw.get("resultSizeEstimate", len(items)) if isinstance(raw, dict) else len(items)

        # Retrieve exact unread count from UNREAD label if available
        total_unread = total_estimate
        try:
            label_data = gmail.get_unread_label_counts()
            if isinstance(label_data, dict) and "messagesUnread" in label_data:
                total_unread = int(label_data["messagesUnread"])
        except Exception:
            pass

        # Deduplicate items by ID
        seen_ids = set()
        deduped = []
        for m in items:
            mid = m.get("id") if isinstance(m, dict) else str(m)
            if mid and mid not in seen_ids:
                seen_ids.add(mid)
                deduped.append(m)

        details = fetch_message_details(token, deduped)

        return {
            "total_unread": total_unread,
            "fetched_count": len(details),
            "has_more": bool(next_page_token),
            "next_page_token": next_page_token,
            "messages": details,
        }

    @staticmethod
    def list_threads(
        db: Session,
        user_id: int,
        limit: int = 20,
    ):

        try:

            gmail = GoogleConnectorService._gmail(db, user_id)

            return gmail.list_threads(limit)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                gmail = GmailClient(token)

                return gmail.list_threads(limit)

            raise

    @staticmethod
    def list_labels(
        db: Session,
        user_id: int,
    ):

        try:

            gmail = GoogleConnectorService._gmail(db, user_id)

            return gmail.list_labels()

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                gmail = GmailClient(token)

                return gmail.list_labels()

            raise

    @staticmethod
    def send_email(
        db: Session,
        user_id: int,
        to: str,
        subject: str,
        body: str,
    ):

        try:

            gmail = GoogleConnectorService._gmail(db, user_id)

            return gmail.send_email(
                to,
                subject,
                body,
            )

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                gmail = GmailClient(token)

                return gmail.send_email(
                    to,
                    subject,
                    body,
                )

            raise

    @staticmethod
    def create_draft(
        db: Session,
        user_id: int,
        to: str,
        subject: str,
        body: str,
    ):

        try:

            gmail = GoogleConnectorService._gmail(db, user_id)

            return gmail.create_draft(
                to,
                subject,
                body,
            )

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                gmail = GmailClient(token)

                return gmail.create_draft(
                    to,
                    subject,
                    body,
                )

            raise

    @staticmethod
    def get_profile(
        db: Session,
        user_id: int,
    ):
        gmail = GoogleConnectorService._gmail(db, user_id)
        return gmail.get_profile()

    @staticmethod
    def list_gmail_messages(
        db: Session,
        user_id: int,
        limit: int = 20,
    ):
        # `limit` used to be passed positionally into the `user_id` slot, so
        # every call looked up a Google grant for user 20 and fell into the
        # fabricated-message branch below it. Both are gone.
        return GoogleConnectorService.list_message_details(
            db,
            user_id=user_id,
            limit=limit,
        )

    @staticmethod
    def list_gmail_threads(
        db: Session,
        user_id: int,
        limit: int = 20,
    ):
        return GoogleConnectorService.list_threads(
            db,
            user_id=user_id,
            limit=limit,
        )

    @staticmethod
    def get_gmail_message(
        db: Session,
        user_id: int,
        message_id: str,
    ):
        gmail = GoogleConnectorService._gmail(db, user_id)
        return gmail.get_message_details(message_id)

    @staticmethod
    def get_gmail_thread(
        db: Session,
        user_id: int,
        thread_id: str,
    ):
        gmail = GoogleConnectorService._gmail(db, user_id)
        return gmail.get_thread_details(thread_id)