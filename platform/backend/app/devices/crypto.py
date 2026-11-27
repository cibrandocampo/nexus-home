"""Device tokens at rest: Fernet (AES-128-CBC + HMAC-SHA256) with DEVICE_TOKEN_KEY.

Losing or changing the key makes every stored token unreadable: the admin re-enters them
(`device_token_unreadable`). Tokens are never logged.
"""

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.core.errors import AppError

TOKEN_UNREADABLE = AppError(
    409,
    "device_token_unreadable",
    "The stored device token cannot be decrypted (DEVICE_TOKEN_KEY changed): re-enter it",
)


def _fernet() -> Fernet:
    return Fernet(get_settings().device_token_key.encode())


def encrypt_token(token: str) -> str:
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    try:
        return _fernet().decrypt(encrypted.encode()).decode()
    except InvalidToken:
        raise TOKEN_UNREADABLE from None
