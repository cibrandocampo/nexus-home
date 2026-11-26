import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError

from app.auth import otp, sessions
from app.auth.models import FailedLogin, LoginCode, RefreshToken
from app.core import scheduler
from app.core.db import get_sessionmaker
from app.core.security import create_access_token
from app.users.models import AuthMethod, Role, User
from tests.helpers import auth

LONG_AGO = datetime.now(UTC) - timedelta(days=30)


async def _count(db, model, *where) -> int:
    return await db.scalar(select(func.count()).select_from(model).where(*where))


async def test_cleanup_removes_only_stale_rows(db, make_user):
    user = await make_user()
    await otp.issue_code(db, user)
    expired = LoginCode(user_id=user.id, code_hash="x" * 64, expires_at=LONG_AGO)
    db.add_all(
        [
            expired,
            FailedLogin(user_id=user.id, created_at=LONG_AGO),
            FailedLogin(user_id=user.id),
        ]
    )
    fresh = await sessions.issue(db, user)
    old = await sessions.issue(db, user)
    await db.commit()
    token = await db.scalar(
        select(RefreshToken).where(RefreshToken.token_hash != "").order_by(RefreshToken.id.desc())
    )
    token.expires_at = LONG_AGO
    await db.commit()

    await scheduler.cleanup(db)

    assert await _count(db, LoginCode) == 1
    assert await _count(db, FailedLogin) == 1
    assert await _count(db, RefreshToken) == 1
    assert fresh and old


async def test_cleanup_deletes_old_unconfirmed_sign_ups_only(db, make_user):
    stale = await make_user(
        "stale@example.com",
        role=Role.none,
        auth_method=AuthMethod.otp,
        password=None,
        created_at=LONG_AGO,
    )
    await make_user("recent@example.com", role=Role.none, auth_method=AuthMethod.otp, password=None)
    await make_user(
        "verified@example.com",
        auth_method=AuthMethod.otp,
        password=None,
        created_at=LONG_AGO,
        email_verified_at=LONG_AGO,
    )
    await make_user("admin-made@example.com", created_at=LONG_AGO)  # password user
    await make_user(
        "disabled@example.com",
        role=Role.none,
        auth_method=AuthMethod.otp,
        password=None,
        created_at=LONG_AGO,
        is_active=False,
    )
    stale_id = stale.id

    await scheduler.cleanup(db)

    db.expire_all()
    emails = set(await db.scalars(select(User.email)))
    assert emails == {
        "recent@example.com",
        "verified@example.com",
        "admin-made@example.com",
        "disabled@example.com",  # an admin disabled it: kept so the address stays blocked
    }
    assert await db.get(User, stale_id) is None


async def test_cleanup_forgets_idle_rate_limit_keys(db, monkeypatch):
    from app.core import ratelimit
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)
    clock = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: clock[0])
    ratelimit.REFRESH_IP.hit("idle")
    clock[0] += 30
    ratelimit.REFRESH_IP.hit("busy")
    clock[0] += 40  # "idle" is now outside the 60 s window, "busy" is not

    await scheduler.cleanup(db)

    assert set(ratelimit.REFRESH_IP._hits) == {"busy"}


async def test_loop_runs_the_cleanup_until_stopped(monkeypatch):
    calls = AsyncMock()
    monkeypatch.setattr(scheduler, "cleanup", calls)

    task = scheduler.start(interval=0.01)
    await asyncio.sleep(0.05)
    await scheduler.stop(task)

    assert calls.await_count >= 2
    assert task.cancelled()


async def test_a_failing_cleanup_does_not_stop_the_loop(monkeypatch, caplog):
    calls = AsyncMock(side_effect=RuntimeError("boom"))
    monkeypatch.setattr(scheduler, "cleanup", calls)

    task = scheduler.start(interval=0.01)
    await asyncio.sleep(0.05)
    await scheduler.stop(task)

    assert calls.await_count >= 2
    assert "Periodic clean-up failed" in caplog.text


async def test_cleanup_and_an_admin_delete_of_a_stale_sign_up_never_deadlock(client, db, make_user):
    admin = await make_user("boss@example.com", role=Role.admin)
    headers = auth(create_access_token(admin.id, "admin"))
    for round_ in range(10):
        stale = await make_user(
            f"stale{round_}@example.com",
            role=Role.none,
            auth_method=AuthMethod.otp,
            password=None,
            created_at=LONG_AGO,
        )
        for _ in range(5):
            db.add(LoginCode(user_id=stale.id, code_hash="x" * 64, expires_at=LONG_AGO))
        await db.commit()

        async def run_cleanup():
            async with get_sessionmaker()() as own:
                await scheduler.cleanup(own)

        response, cleaned = await asyncio.gather(
            client.delete(f"/api/users/{stale.id}", headers=headers),
            run_cleanup(),
            return_exceptions=True,
        )

        assert cleaned is None, repr(cleaned)
        assert response.status_code in (204, 404), response.text


@pytest.mark.parametrize("role", [Role.user, Role.admin])
async def test_cleanup_keeps_a_stale_sign_up_an_admin_gave_a_role(db, make_user, role):
    await make_user(
        "promoted@example.com",
        role=role,
        auth_method=AuthMethod.otp,
        password=None,
        created_at=LONG_AGO,
    )

    await scheduler.cleanup(db)

    db.expire_all()
    assert await db.scalar(select(User.email)) == "promoted@example.com"


async def test_cleanup_skips_rows_another_transaction_holds(db, make_user):
    stale = await make_user(
        "stale@example.com",
        role=Role.none,
        auth_method=AuthMethod.otp,
        password=None,
        created_at=LONG_AGO,
    )
    other = await make_user("other@example.com")
    db.add(LoginCode(user_id=other.id, code_hash="x" * 64, expires_at=LONG_AGO))
    await db.commit()
    stale_id = stale.id

    async with get_sessionmaker()() as holder:
        await holder.execute(select(User).where(User.id == stale_id).with_for_update())
        await holder.execute(select(LoginCode).with_for_update())
        async with get_sessionmaker()() as own:
            await asyncio.wait_for(scheduler.cleanup(own), timeout=2)  # does not wait
        await holder.rollback()

    db.expire_all()
    assert await db.get(User, stale_id) is not None
    assert await _count(db, LoginCode) == 1


async def test_cleanup_gives_up_on_a_statement_that_would_wait(db, make_user, caplog):
    """A stale sign-up whose token another transaction holds: the users statement would wait on
    the cascade. It times out quickly, is skipped, and the rest of the clean-up still runs."""
    stale = await make_user(
        "stale@example.com",
        role=Role.none,
        auth_method=AuthMethod.otp,
        password=None,
        created_at=LONG_AGO,
    )
    await sessions.issue(db, stale)
    other = await make_user("other@example.com")
    db.add(LoginCode(user_id=other.id, code_hash="x" * 64, expires_at=LONG_AGO))
    await db.commit()
    stale_id = stale.id

    async with get_sessionmaker()() as holder:
        await holder.execute(
            select(RefreshToken).where(RefreshToken.user_id == stale_id).with_for_update()
        )
        async with get_sessionmaker()() as own:
            with caplog.at_level("INFO", logger="app.core.scheduler"):
                await asyncio.wait_for(scheduler.cleanup(own), timeout=2)
        await holder.rollback()

    db.expire_all()
    assert await db.get(User, stale_id) is not None  # retried next run
    assert await _count(db, LoginCode) == 0  # the later statements ran
    assert "skipped busy rows" in caplog.text


async def test_cleanup_raises_other_database_errors(db, monkeypatch):
    class Boom(Exception):
        sqlstate = "XX000"

    async def failing(statement, *args, **kwargs):
        if "lock_timeout" in str(statement):
            return None
        raise DBAPIError("DELETE", {}, Boom())

    monkeypatch.setattr(db, "execute", failing)

    with pytest.raises(DBAPIError):
        await scheduler.cleanup(db)
