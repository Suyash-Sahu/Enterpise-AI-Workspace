from app.services.google_connector_service import GoogleConnectorService


class GoogleDocProcessor:

    @staticmethod
    def extract(
        db,
        user_id: int,
        file_id: str,
    ) -> str:

        return GoogleConnectorService.export_google_doc(
            db=db,
            user_id=user_id,
            file_id=file_id,
        )