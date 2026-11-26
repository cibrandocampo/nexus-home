"""Creates the first administrator from ADMIN_EMAIL / ADMIN_PASSWORD."""

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.core.security import hash_password_async, validate_password
from app.users.models import AuthMethod, Role, User, normalise_email

log = logging.getLogger(__name__)


async def ensure_admin(db: AsyncSession) -> User | None:
    """Create the admin when both variables are set and no admin exists. Never edits a user.

    Raises RuntimeError when the configured password breaks the password rules, so a weak
    admin password stops the start-up instead of being accepted silently.
    """
    settings = get_settings()
    if not settings.admin_email or not settings.admin_password:
        return None
    if await db.scalar(select(func.count()).select_from(User).where(User.role == Role.admin)):
        return None
    email = normalise_email(settings.admin_email)
    if await db.scalar(select(User).where(User.email == email)):
        log.warning("ADMIN_EMAIL belongs to an existing non-admin user: not changed")
        return None
    try:
        validate_password(settings.admin_password, email)
    except AppError as exc:
        raise RuntimeError(f"ADMIN_PASSWORD rejected: {exc.message}") from exc
    admin = User(
        email=email,
        auth_method=AuthMethod.password,
        password_hash=await hash_password_async(settings.admin_password),
        role=Role.admin,
        is_active=True,
        email_verified_at=datetime.now(UTC),  # vouched for by whoever set ADMIN_EMAIL
    )
    db.add(admin)
    try:
        await db.commit()
    except IntegrityError:  # another instance created it at the same time
        await db.rollback()
        return None
    log.info("Created the first administrator from ADMIN_EMAIL")
    return admin
