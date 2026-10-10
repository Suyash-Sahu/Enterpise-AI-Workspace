import re
from app.processors.docx_processor import DOCXProcessor
from app.processors.google_doc_processor import GoogleDocProcessor
from app.processors.pdf_processor import PDFProcessor
from app.processors.txt_processor import TXTProcessor
from app.services.google_connector_service import GoogleConnectorService


class DocumentProcessor:

    @staticmethod
    def clean_text(text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        lines = []
        for line in text.split("\n"):
            cleaned_line = re.sub(r"[ \t]+", " ", line).strip()
            lines.append(cleaned_line)

        cleaned_text = "\n".join(lines)
        cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

        return cleaned_text.strip()

    @staticmethod
    def extract_metadata(text: str, source: str = "document.pdf") -> dict:
        clean = DocumentProcessor.clean_text(text)
        words = clean.split()
        word_count = len(words)
        char_count = len(clean)

        est_pages = max(1, (word_count + 250) // 300)

        extension = "txt"
        if "." in source:
            extension = source.rsplit(".", 1)[-1].lower()

        return {
            "source": source,
            "extension": extension,
            "word_count": word_count,
            "char_count": char_count,
            "estimated_pages": est_pages,
        }

    @staticmethod
    def extract(
        db,
        user_id: int,
        file: dict,
    ) -> str:

        mime = file.get(
            "mimeType",
            "",
        )

        file_id = file["id"]

        # Google Docs
        if mime == "application/vnd.google-apps.document":

            return GoogleDocProcessor.extract(
                db,
                user_id,
                file_id,
            )

        # Download binary file
        data = GoogleConnectorService.download_drive_file(
            db=db,
            user_id=user_id,
            file_id=file_id,
        )

        # PDF
        if mime == "application/pdf":

            return PDFProcessor.extract(
                data
            )

        # DOCX
        if (
            mime
            == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ):

            return DOCXProcessor.extract(
                data
            )

        # TXT
        if mime.startswith("text/"):

            return TXTProcessor.extract(
                data
            )

        raise ValueError(
            f"Unsupported MIME type: {mime}"
        )