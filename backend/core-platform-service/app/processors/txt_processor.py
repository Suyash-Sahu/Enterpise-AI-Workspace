class TXTProcessor:

    @staticmethod
    def extract(
        data: bytes,
    ) -> str:

        return data.decode(
            "utf-8",
            errors="ignore",
        )