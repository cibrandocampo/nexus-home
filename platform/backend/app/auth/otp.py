"""One-time login codes sent by email."""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginCode
from app.core.config import get_settings
from app.core.security import hash_token
from app.users.models import User


def _now() -> datetime:
    return datetime.now(UTC)


async def issue_code(db: AsyncSession, user: User) -> str:
    """Create a 6-digit code for the user and return it (only its hash is stored)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    db.add(
        LoginCode(
            user_id=user.id,
            code_hash=hash_token(code),
            expires_at=_now() + timedelta(minutes=get_settings().otp_minutes),
        )
    )
    await db.commit()
    return code


async def verify_code(db: AsyncSession, user: User, code: str) -> bool:
    """Check `code` against the user's newest live code; wrong guesses count as attempts
    (committed). A right code is marked consumed but not committed: the caller commits it with
    the session it creates, in the same transaction."""
    settings = get_settings()
    current = await db.scalar(
        select(LoginCode)
        .where(
            LoginCode.user_id == user.id,
            LoginCode.consumed_at.is_(None),
            LoginCode.expires_at > _now(),
        )
        .order_by(LoginCode.created_at.desc(), LoginCode.id.desc())
        .limit(1)
        .with_for_update()
    )
    if current is None or current.attempts >= settings.otp_max_attempts:
        await db.rollback()
        return False
    if not secrets.compare_digest(current.code_hash, hash_token(code.strip())):
        current.attempts += 1
        await db.commit()
        return False
    current.consumed_at = _now()
    return True
