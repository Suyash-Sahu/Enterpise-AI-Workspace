import threading
from concurrent.futures import ThreadPoolExecutor

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


def fetch_message_details(access_token: str, messages: list) -> list:
    """Fetch each message body concurrently, preserving the listed order."""
    message_ids = [m["id"] for m in messages if m.get("id")]

    if not message_ids:
        return []

    def fetch(message_id: str):
        return _thread_gmail_client(access_token).get_message_details(message_id)

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
        limit: int = 20,
    ):

        token = TokenService.get_google_token(db, user_id=user_id)

        try:

            messages = GmailClient(token).unread_messages(limit)

        except requests.exceptions.HTTPError as e:

            if (
                e.response is not None
                and e.response.status_code == 401
            ):

                token = TokenService.force_refresh_google_token(db, user_id=user_id)

                messages = GmailClient(token).unread_messages(limit)

            else:

                raise

        return fetch_message_details(token, messages)

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