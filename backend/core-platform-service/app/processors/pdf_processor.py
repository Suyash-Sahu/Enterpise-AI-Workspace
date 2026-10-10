from io import BytesIO

from pypdf import PdfReader


class PDFProcessor:

    @staticmethod
    def extract(
        data: bytes,
    ) -> str:

        pdf = PdfReader(
            BytesIO(data)
        )

        text = ""

        for page in pdf.pages:

            page_text = page.extract_text()

            if page_text:
                text += page_text + "\n"

        return text