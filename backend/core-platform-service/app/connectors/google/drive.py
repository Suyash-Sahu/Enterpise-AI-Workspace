from googleapiclient.http import MediaIoBaseDownload
from io import BytesIO
from app.connectors.google.google_service import GoogleService

class GoogleDriveClient:

    def __init__(self, access_token: str):

        self.service = GoogleService.build_service(
            "drive",
            "v3",
            access_token,
        )

    def list_files(self):
        result = (
            self.service.files()
            .list(
                pageSize=20,
                fields="files(id,name,mimeType,modifiedTime,size)"
            )
            .execute()
        )

        return result.get("files", [])

    def get_file(self, file_id: str):
        return (
            self.service.files()
            .get(
                fileId=file_id,
                fields="*",
            )
            .execute()
        )

    def download_file(self, file_id: str):
        request = self.service.files().get_media(fileId=file_id)

        file = BytesIO()

        downloader = MediaIoBaseDownload(file, request)

        done = False

        while not done:
            _, done = downloader.next_chunk()

        file.seek(0)

        return file.read()

    def export_google_doc(self, file_id: str):
        request = (
            self.service.files()
            .export_media(
                fileId=file_id,
                mimeType="text/plain",
            )
        )

        file = BytesIO()

        downloader = MediaIoBaseDownload(file, request)

        done = False

        while not done:
            _, done = downloader.next_chunk()

        file.seek(0)

        return file.read().decode()

    def search_files(
        self,
        query: str,
    ):

        result = (
            self.service.files()
            .list(
                q=f"name contains '{query}'",
                fields="files(id,name,mimeType,modifiedTime,size)",
            )
            .execute()
        )

        return result.get("files", [])

    def recent_files(
        self,
        limit: int = 10,
    ):

        result = (
            self.service.files()
            .list(
                pageSize=limit,
                orderBy="modifiedTime desc",
                fields="files(id,name,mimeType,modifiedTime,size)",
            )
            .execute()
        )

        return result.get("files", [])

    def folders(
        self,
    ):

        result = (
            self.service.files()
            .list(
                q="mimeType='application/vnd.google-apps.folder'",
                fields="files(id,name)",
            )
            .execute()
        )

        return result.get("files", [])

    def file_details(
        self,
        file_id: str,
    ):

        return (
            self.service.files()
            .get(
                fileId=file_id,
                fields="*",
            )
            .execute()
        )