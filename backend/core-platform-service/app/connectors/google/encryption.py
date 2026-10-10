from cryptography.fernet import Fernet

from app.core.config import settings

cipher = Fernet(settings.FERNET_KEY.encode())


def encrypt(value: str) -> str:
    return cipher.encrypt(
        value.encode()
    ).decode()


def decrypt(value: str) -> str:
    return cipher.decrypt(
        value.encode()
    ).decode()