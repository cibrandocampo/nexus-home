"""Password hashing and rules, access tokens, random refresh tokens."""

import asyncio
import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.errors import AppError

PASSWORD_MIN_LENGTH = 10
PASSWORD_MAX_BYTES = 72  # bcrypt only uses the first 72 bytes
ALGORITHM = "HS256"


def validate_password(password: str, email: str) -> None:
    """Raise AppError(400, "weak_password") when the password breaks a rule."""
    if len(password) < PASSWORD_MIN_LENGTH:
        reason = f"Password must have at least {PASSWORD_MIN_LENGTH} characters"
    elif len(password.encode()) > PASSWORD_MAX_BYTES:
        reason = f"Password must have at most {PASSWORD_MAX_BYTES} bytes"
    elif password.isdigit():
        reason = "Password cannot be only digits"
    elif password.strip().lower() == email.strip().lower():
        reason = "Password cannot be the email address"
    else:
        return
    raise AppError(400, "weak_password", reason)


def hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=get_settings().bcrypt_rounds)
    return bcrypt.hashpw(password.encode(), salt).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or len(password.encode()) > PASSWORD_MAX_BYTES:
        return False
    return bcrypt.checkpw(password.encode(), password_hash.encode())


async def hash_password_async(password: str) -> str:
    """hash_password off the event loop: bcrypt takes ~0.3 s and would block every request."""
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, password_hash: str | None) -> bool:
    return await asyncio.to_thread(verify_password, password, password_hash)


def create_access_token(user_id: int, role: str, now: datetime | None = None) -> str:
    settings = get_settings()
    issued = now or datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": issued,
        "exp": issued + timedelta(minutes=settings.access_token_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.secret_key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> int:
    """Return the user id of a valid access token, else raise AppError(401)."""
    try:
        claims = jwt.decode(
            token,
            get_settings().secret_key,
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "iat", "type"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AppError(401, "token_expired", "Access token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise AppError(401, "unauthorized", "Invalid access token") from exc
    if claims["type"] != "access" or not str(claims["sub"]).isdigit():
        raise AppError(401, "unauthorized", "Invalid access token")
    return int(claims["sub"])


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()
