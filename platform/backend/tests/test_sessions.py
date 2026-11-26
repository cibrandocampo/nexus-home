import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import Response
from sqlalchemy import select

from app.auth import sessions
from app.auth.models import RefreshToken
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.core.security import decode_access_token, hash_token


async def _token(db, raw) -> RefreshToken:
    query = select(RefreshToken).where(RefreshToken.token_hash == hash_token(raw))
    return await db.scalar(query.execution_options(populate_existing=True))


async def test_issue_returns_a_valid_access_token_and_stores_the_refresh_token_hashed(
    db, make_user
):
    user = await make_user()

    session = await sessions.issue(db, user)

    assert decode_access_token(session.access_token) == user.id
    stored = await _token(db, session.refresh_token)
    assert stored.user_id == user.id
    assert stored.revoked_at is None
    assert stored.token_hash != session.refresh_token


async def test_rotate_revokes_the_old_token_and_keeps_the_family(db, make_user):
    user = await make_user()
    first = await sessions.issue(db, user)

    second = await sessions.rotate(db, first.refresh_token)

    old, new = await _token(db, first.refresh_token), await _token(db, second.refresh_token)
    assert old.revoked_at is not None
    assert old.replaced_by_id == new.id
    assert new.family_id == old.family_id
    assert new.revoked_at is None


async def _age_revocation(db, raw, seconds):
    token = await _token(db, raw)
    token.revoked_at = datetime.now(UTC) - timedelta(seconds=seconds)
    await db.commit()


async def test_reusing_a_rotated_token_after_the_grace_window_revokes_the_family(db, make_user):
    user = await make_user()
    first = await sessions.issue(db, user)
    second = await sessions.rotate(db, first.refresh_token)
    await _age_revocation(db, first.refresh_token, 11)

    with pytest.raises(AppError) as error:
        await sessions.rotate(db, first.refresh_token)

    assert error.value.status == 401
    assert (await _token(db, second.refresh_token)).revoked_at is not None


async def test_reusing_a_just_rotated_token_is_refused_but_keeps_the_session(db, make_user):
    user = await make_user()
    first = await sessions.issue(db, user)
    second = await sessions.rotate(db, first.refresh_token)

    with pytest.raises(AppError) as error:
        await sessions.rotate(db, first.refresh_token)

    assert error.value.status == 401
    assert (await _token(db, second.refresh_token)).revoked_at is None


async def test_reusing_a_logged_out_token_revokes_the_family_at_once(db, make_user):
    user = await make_user()
    first = await sessions.issue(db, user)
    second = await sessions.rotate(db, first.refresh_token)
    await sessions.revoke(db, second.refresh_token)
    third = await sessions.issue(db, user)  # another session, other family

    with pytest.raises(AppError):
        await sessions.rotate(db, second.refresh_token)

    assert (await _token(db, third.refresh_token)).revoked_at is None


async def test_concurrent_rotations_of_one_token_let_only_one_succeed(db, make_user):
    user = await make_user()
    session = await sessions.issue(db, user)

    async def attempt():
        async with get_sessionmaker()() as own_db:
            return await sessions.rotate(own_db, session.refresh_token)

    results = await asyncio.gather(*(attempt() for _ in range(3)), return_exceptions=True)

    winners = [r for r in results if isinstance(r, sessions.Session)]
    assert len(winners) == 1
    assert all(isinstance(r, AppError) and r.status == 401 for r in results if r not in winners)
    live = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.family_id == (await _token(db, session.refresh_token)).family_id,
            RefreshToken.revoked_at.is_(None),
        )
    )
    assert [t.token_hash for t in live] == [hash_token(winners[0].refresh_token)]


async def test_reuse_does_not_touch_other_sessions_of_the_user(db, make_user):
    user = await make_user()
    stolen = await sessions.issue(db, user)
    await sessions.rotate(db, stolen.refresh_token)
    await _age_revocation(db, stolen.refresh_token, 11)
    other = await sessions.issue(db, user)

    with pytest.raises(AppError):
        await sessions.rotate(db, stolen.refresh_token)

    assert (await _token(db, other.refresh_token)).revoked_at is None


@pytest.mark.parametrize("raw", [None, "", "never-issued"])
async def test_rotate_rejects_missing_or_unknown_tokens(db, raw):
    with pytest.raises(AppError) as error:
        await sessions.rotate(db, raw)

    assert (error.value.status, error.value.code) == (401, "unauthorized")


async def test_rotate_rejects_an_expired_token(db, make_user):
    user = await make_user()
    session = await sessions.issue(db, user)
    stored = await _token(db, session.refresh_token)
    stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.commit()

    with pytest.raises(AppError):
        await sessions.rotate(db, session.refresh_token)

    assert (await _token(db, session.refresh_token)).revoked_at is not None


async def test_rotate_rejects_a_deactivated_user(db, make_user):
    user = await make_user()
    session = await sessions.issue(db, user)
    user.is_active = False
    await db.commit()

    with pytest.raises(AppError):
        await sessions.rotate(db, session.refresh_token)


async def test_revoke_ends_one_session_and_ignores_unknown_tokens(db, make_user):
    user = await make_user()
    session = await sessions.issue(db, user)

    await sessions.revoke(db, session.refresh_token)
    await sessions.revoke(db, "never-issued")
    await sessions.revoke(db, None)

    assert (await _token(db, session.refresh_token)).revoked_at is not None


async def test_revoke_all_ends_every_session_of_one_user_only(db, make_user):
    user = await make_user()
    other_user = await make_user("other@example.com")
    a, b = await sessions.issue(db, user), await sessions.issue(db, user)
    other = await sessions.issue(db, other_user)

    await sessions.revoke_all(db, user.id)

    assert (await _token(db, a.refresh_token)).revoked_at is not None
    assert (await _token(db, b.refresh_token)).revoked_at is not None
    assert (await _token(db, other.refresh_token)).revoked_at is None


@pytest.mark.parametrize("secure", [True, False])
def test_refresh_cookie_attributes(monkeypatch, secure):
    monkeypatch.setattr(get_settings(), "cookie_secure", secure)
    response = Response()

    sessions.set_refresh_cookie(response, "raw-token")

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("refresh_token=raw-token;")
    assert "HttpOnly" in cookie
    assert "Path=/api/auth" in cookie
    assert "SameSite=strict" in cookie
    assert f"Max-Age={30 * 86400}" in cookie
    assert ("Secure" in cookie) is secure


def test_clear_refresh_cookie_expires_it_on_the_same_path():
    response = Response()

    sessions.clear_refresh_cookie(response)

    cookie = response.headers["set-cookie"]
    assert cookie.startswith('refresh_token="";')
    assert "Max-Age=0" in cookie
    assert "Path=/api/auth" in cookie
