import asyncio
import logging
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, func, select, update

from app.auth import otp, sessions
from app.auth.models import FailedLogin, RefreshToken
from app.core import security
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.core.security import create_access_token
from app.users.models import AuthMethod, Role, User
from tests.helpers import auth

WRONG = {"email": "ana@example.com", "password": "wrong password!"}


def _slow_wrong_password(calls: list):
    def verify(password, password_hash):
        calls.append(password)
        time.sleep(0.2)  # like bcrypt at 12 rounds: blocks whichever thread runs it
        return False

    return verify


async def test_password_check_does_not_block_other_requests(client, make_user, monkeypatch):
    await make_user("ana@example.com")
    monkeypatch.setattr(security, "verify_password", _slow_wrong_password([]))
    finished = []

    async def login():
        await client.post("/api/auth/login/verify", json=WRONG)
        finished.append("login")

    async def health():
        await asyncio.sleep(0.05)  # starts while the password is being checked
        await client.get("/api/health")
        finished.append("health")

    await asyncio.gather(login(), health())

    assert finished == ["health", "login"]


async def test_concurrent_wrong_passwords_cannot_exceed_the_lockout(
    client, db, make_user, monkeypatch
):
    user = await make_user("ana@example.com")
    calls = []
    monkeypatch.setattr(security, "verify_password", _slow_wrong_password(calls))

    responses = await asyncio.gather(
        *(client.post("/api/auth/login/verify", json=WRONG) for _ in range(12))
    )

    codes = sorted(r.json()["error"]["code"] for r in responses)
    assert codes == ["invalid_credentials"] * 5 + ["locked"] * 7
    assert len(calls) == 5
    failures = await db.scalar(
        select(func.count()).select_from(FailedLogin).where(FailedLogin.user_id == user.id)
    )
    assert failures == 5


async def test_reuse_log_names_only_the_user_id_and_family(db, make_user, caplog):
    user = await make_user("ana@example.com")
    first = await sessions.issue(db, user)
    await sessions.rotate(db, first.refresh_token)
    await db.execute(
        update(RefreshToken)
        .where(RefreshToken.revoked_at.is_not(None))
        .values(revoked_at=datetime.now(UTC) - timedelta(minutes=1))
    )
    await db.commit()

    with (
        caplog.at_level(logging.WARNING, logger="app.auth.sessions"),
        pytest.raises(AppError),
    ):
        await sessions.rotate(db, first.refresh_token)

    [record] = caplog.records
    assert f"of user {user.id} revoked" in record.getMessage()
    assert "ana@example.com" not in record.getMessage()
    assert first.refresh_token not in record.getMessage()


async def test_account_disabled_while_waiting_for_the_lock_is_refused(client, db, make_user):
    user = await make_user("ana@example.com")
    async with get_sessionmaker()() as holder:
        await holder.execute(select(User).where(User.id == user.id).with_for_update(key_share=True))
        login = asyncio.create_task(
            client.post(
                "/api/auth/login/verify",
                json={"email": "ana@example.com", "password": "correct horse battery"},
            )
        )
        await asyncio.sleep(0.1)  # the login is now waiting for the row lock
        await holder.execute(update(User).where(User.id == user.id).values(is_active=False))
        await holder.commit()

    response = await login

    assert response.json()["error"]["code"] == "account_disabled"


async def test_a_refresh_waiting_on_a_user_change_sees_its_revocation(db, make_user):
    user = await make_user("ana@example.com")
    session = await sessions.issue(db, user)

    async def refresh():
        async with get_sessionmaker()() as own:
            return await sessions.rotate(own, session.refresh_token)

    async with get_sessionmaker()() as admin_tx:  # e.g. an admin resetting the password
        await sessions.lock_user(admin_tx, user.id)
        task = asyncio.create_task(refresh())
        await asyncio.sleep(0.2)  # the refresh waits for the user's row
        await sessions.revoke_all(admin_tx, user.id, commit=False)
        await admin_tx.commit()

    with pytest.raises(AppError) as error:
        await task

    assert error.value.status == 401
    live = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert live.all() == []


async def _delete_while_waiting(user_id: int, start):
    """Hold the user's row as an admin delete would, start `start()`, then delete the user."""
    async with get_sessionmaker()() as holder:
        await holder.execute(select(User).where(User.id == user_id).with_for_update())
        task = asyncio.create_task(start())
        await asyncio.sleep(0.2)  # the request now waits for the user's row
        await holder.execute(delete(User).where(User.id == user_id))
        await holder.commit()
    return await task


async def test_refresh_of_a_user_deleted_meanwhile_is_unauthorized(db, make_user):
    user = await make_user("ana@example.com")
    session = await sessions.issue(db, user)

    async def refresh():
        async with get_sessionmaker()() as own:
            return await sessions.rotate(own, session.refresh_token)

    with pytest.raises(AppError) as error:
        await _delete_while_waiting(user.id, refresh)

    assert (error.value.status, error.value.code) == (401, "unauthorized")


@pytest.mark.parametrize("method", ["password", "code"])
async def test_login_of_a_user_deleted_meanwhile_is_invalid_credentials(
    client, db, make_user, method
):
    if method == "password":
        user = await make_user("ana@example.com")
        body = {"email": "ana@example.com", "password": "correct horse battery"}
    else:
        user = await make_user(
            "ana@example.com",
            auth_method=AuthMethod.otp,
            password=None,
            email_verified_at=datetime.now(UTC),
        )
        body = {"email": "ana@example.com", "code": await otp.issue_code(db, user)}

    response = await _delete_while_waiting(
        user.id, lambda: client.post("/api/auth/login/verify", json=body)
    )

    assert response.json()["error"]["code"] == "invalid_credentials"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("patch", "/api/auth/me", {"first_name": "Ana"}),
        (
            "post",
            "/api/auth/change-password",
            {"current_password": "correct horse battery", "new_password": "a new long password"},
        ),
    ],
)
async def test_own_requests_of_a_user_deleted_meanwhile_are_unauthorized(
    client, make_user, method, path, body
):
    user = await make_user("ana@example.com")
    headers = auth(create_access_token(user.id, "user"))

    response = await _delete_while_waiting(
        user.id, lambda: client.request(method, path, headers=headers, json=body)
    )

    assert response.status_code == 401


async def test_issuing_a_session_for_a_deleted_user_is_unauthorized(db, make_user):
    user = await make_user("ana@example.com")
    await db.execute(delete(User).where(User.id == user.id))
    await db.commit()

    with pytest.raises(AppError) as error:
        await sessions.issue(db, user)

    assert error.value.status == 401


async def test_deleting_a_user_while_their_sessions_refresh_never_deadlocks(client, db, make_user):
    admin = await make_user("admin@example.com", role=Role.admin)
    user = await make_user("ana@example.com")
    user_id, admin_id = user.id, admin.id
    raws = [(await sessions.issue(db, user)).refresh_token for _ in range(8)]

    async def refresh(raw):
        async with get_sessionmaker()() as own:
            return await sessions.rotate(own, raw)

    results = await asyncio.gather(
        client.delete(
            f"/api/users/{user_id}", headers=auth(create_access_token(admin_id, "admin"))
        ),
        *(refresh(raw) for raw in raws),
        return_exceptions=True,
    )

    deleted, *refreshes = results
    assert deleted.status_code == 204
    for result in refreshes:
        assert isinstance(result, sessions.Session) or (
            isinstance(result, AppError) and result.status == 401
        ), repr(result)
    db.expire_all()
    assert await db.get(User, user_id) is None


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/users/{id}/set-password", {"password": "a brand new one"}),
        ("/api/users/{id}", {"role": "none"}),
    ],
)
async def test_no_session_survives_an_admin_reset_while_refreshing(
    client, db, make_user, path, body
):
    admin = await make_user("admin@example.com", role=Role.admin)
    user = await make_user("ana@example.com")
    user_id, admin_id = user.id, admin.id
    raws = [(await sessions.issue(db, user)).refresh_token for _ in range(8)]

    async def refresh(raw):
        async with get_sessionmaker()() as own:
            return await sessions.rotate(own, raw)

    method = "post" if "set-password" in path else "patch"
    await asyncio.gather(
        client.request(
            method,
            path.format(id=user_id),
            json=body,
            headers=auth(create_access_token(admin_id, "admin")),
        ),
        *(refresh(raw) for raw in raws),
        return_exceptions=True,
    )

    db.expire_all()
    live = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    assert live.all() == []


async def test_login_start_for_a_user_deleted_meanwhile_is_not_found(client, make_user):
    user = await make_user(
        "ana@example.com",
        auth_method=AuthMethod.otp,
        password=None,
        email_verified_at=datetime.now(UTC),
    )

    response = await _delete_while_waiting(
        user.id, lambda: client.post("/api/auth/login/start", json={"email": "ana@example.com"})
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"


async def test_parallel_sign_ups_of_one_address_create_one_account(client, db, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_self_signup", True)

    responses = await asyncio.gather(
        *(client.post("/api/auth/login/start", json={"email": "new@example.com"}) for _ in range(5))
    )

    assert [r.json() for r in responses] == [{"method": "otp"}] * 5
    count = await db.scalar(
        select(func.count()).select_from(User).where(User.email == "new@example.com")
    )
    assert count == 1
