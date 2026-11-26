"""Periodic clean-ups run inside the app process (one instance assumed)."""

import asyncio
import contextlib
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import FailedLogin, LoginCode, RefreshToken
from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.users.models import AuthMethod, Role, User

log = logging.getLogger(__name__)

INTERVAL_SECONDS = 3600
LOCK_TIMEOUT_MS = 200  # below Postgres' deadlock_timeout (1 s)
LOCK_NOT_AVAILABLE = "55P03"


def _skip_locked(model, *conditions):
    """DELETE of the rows matching `conditions` that nobody else has locked right now.

    Rows a request holds are left for the next run. Waits that remain (foreign key actions,
    cascades) are cut by the statement's lock timeout in `cleanup`.
    """
    ids = select(model.id).where(*conditions).with_for_update(skip_locked=True)
    return delete(model).where(model.id.in_(ids.scalar_subquery()))


async def cleanup(db: AsyncSession) -> None:
    """Delete sign-ups never confirmed with a code after `unverified_signup_days` (only those an
    admin has not given a role), expired login codes, old failed logins and refresh tokens expired
    more than 7 days ago; forget rate-limit keys with no recent hits.

    One statement per transaction, users first, locked rows skipped (see `_skip_locked`), and a
    short lock timeout on whatever a statement still has to wait for: the clean-up never waits
    long enough to be part of a deadlock.
    """
    now = datetime.now(UTC)
    settings = get_settings()
    statements = (
        _skip_locked(
            User,
            User.role == Role.none,  # an admin who gave a role vouched for the account
            User.email_verified_at.is_(None),
            User.last_login_at.is_(None),
            User.auth_method == AuthMethod.otp,
            User.is_active.is_(True),  # a pending sign-up an admin disabled stays blocked
            User.created_at < now - timedelta(days=settings.unverified_signup_days),
        ),
        _skip_locked(LoginCode, LoginCode.expires_at < now),
        _skip_locked(FailedLogin, FailedLogin.created_at < now - timedelta(days=1)),
        _skip_locked(RefreshToken, RefreshToken.expires_at < now - timedelta(days=7)),
    )
    for statement in statements:
        try:
            # Anything still waiting (e.g. a cascade reaching a row a request holds) gives up well
            # before Postgres would look for a deadlock; the rows are retried next run.
            await db.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT_MS}ms'"))
            await db.execute(statement)
            await db.commit()
        except DBAPIError as exc:
            await db.rollback()
            if getattr(exc.orig, "sqlstate", None) != LOCK_NOT_AVAILABLE:
                raise
            log.info("Clean-up skipped busy rows; they are retried in the next run")
    for limit in ratelimit.ALL:
        limit.prune()


async def _loop(interval: float) -> None:
    while True:
        try:
            async with get_sessionmaker()() as db:
                await cleanup(db)
        except Exception:
            log.exception("Periodic clean-up failed")
        await asyncio.sleep(interval)


def start(interval: float = INTERVAL_SECONDS) -> asyncio.Task:
    return asyncio.create_task(_loop(interval), name="cleanup")


async def stop(task: asyncio.Task) -> None:
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
