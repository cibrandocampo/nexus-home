from unittest.mock import AsyncMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.security import verify_password
from app.users.bootstrap import ensure_admin
from app.users.models import AuthMethod, Role, User


@pytest.fixture
def admin_env(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "admin_email", " Admin@Example.com ")
    monkeypatch.setattr(settings, "admin_password", "correct horse battery")
    return settings


async def _count(db) -> int:
    return await db.scalar(select(func.count()).select_from(User))


async def test_creates_the_admin_from_the_environment(db, admin_env):
    admin = await ensure_admin(db)

    assert admin.email == "admin@example.com"
    assert admin.role is Role.admin
    assert admin.auth_method is AuthMethod.password
    assert admin.is_active
    assert verify_password("correct horse battery", admin.password_hash)


async def test_second_run_does_nothing(db, admin_env):
    await ensure_admin(db)

    assert await ensure_admin(db) is None
    assert await _count(db) == 1


@pytest.mark.parametrize("missing", ["admin_email", "admin_password"])
async def test_does_nothing_without_both_variables(db, admin_env, monkeypatch, missing):
    monkeypatch.setattr(admin_env, missing, None)

    assert await ensure_admin(db) is None
    assert await _count(db) == 0


async def test_existing_admin_prevents_creation(db, admin_env, make_user):
    await make_user("boss@example.com", role=Role.admin)

    assert await ensure_admin(db) is None
    assert await _count(db) == 1


async def test_existing_non_admin_with_that_email_is_left_unchanged(db, admin_env, make_user):
    user = await make_user("admin@example.com", role=Role.user)

    assert await ensure_admin(db) is None
    await db.refresh(user)
    assert user.role is Role.user


async def test_weak_password_stops_the_start_up(db, admin_env, monkeypatch):
    monkeypatch.setattr(admin_env, "admin_password", "short")

    with pytest.raises(RuntimeError, match="ADMIN_PASSWORD rejected"):
        await ensure_admin(db)
    assert await _count(db) == 0


async def test_concurrent_creation_by_another_instance_is_tolerated(db, admin_env, monkeypatch):
    monkeypatch.setattr(db, "commit", AsyncMock(side_effect=IntegrityError("insert", {}, None)))

    assert await ensure_admin(db) is None
