from io import BytesIO

from docx import Document


class DOCXProcessor:

    @staticmethod
    def extract(
        data: bytes,
    ) -> str:

        doc = Document(
            BytesIO(data)
        )

        return "\n".join(
            paragraph.text
            for paragraph in doc.paragraphs
        )