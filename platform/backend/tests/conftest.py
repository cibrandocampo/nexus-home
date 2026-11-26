"""Test setup: a dedicated Postgres database, migrated once, emptied between tests."""

import os

# Point the app at the test database before anything reads the settings.
os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
os.environ["ENV"] = "test"
os.environ["BCRYPT_ROUNDS"] = "4"  # fast hashing in tests
os.environ["SECRET_KEY"] = "test-secret-key-with-enough-length-for-hs256"
os.environ["EMAIL_BACKEND"] = "memory"
os.environ["RATE_LIMIT_ENABLED"] = "false"  # enabled explicitly by the rate-limit tests
os.environ["ALLOW_SELF_SIGNUP"] = "false"
os.environ["COOKIE_SECURE"] = "false"  # the test client talks plain http

from collections.abc import AsyncIterator

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import Base, get_engine, get_sessionmaker
from app.core.security import hash_password
from app.main import create_app
from app.users.models import AuthMethod, Role, User


@pytest.fixture(scope="session", autouse=True)
def migrated_database() -> None:
    config = Config("alembic.ini")
    command.downgrade(config, "base")
    command.upgrade(config, "head")


@pytest.fixture(autouse=True)
async def clean_tables() -> AsyncIterator[None]:
    yield
    tables = ", ".join(f'"{t.name}"' for t in reversed(Base.metadata.sorted_tables))
    if tables:
        async with get_engine().begin() as conn:
            await conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture(autouse=True)
def fresh_state():
    """Rate-limit counters and the email outbox are process globals: reset them per test."""
    from app.auth.disposable import blocked_domains
    from app.core import ratelimit
    from app.emails import sender

    for limit in ratelimit.ALL:
        limit.reset()
    sender.outbox.clear()
    blocked_domains.cache_clear()
    ratelimit._trusted_networks.cache_clear()
    yield
    blocked_domains.cache_clear()
    ratelimit._trusted_networks.cache_clear()


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app) -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def db() -> AsyncIterator[AsyncSession]:
    async with get_sessionmaker()() as session:
        yield session


@pytest.fixture
def make_user(db):
    """Create a user; password users get `password` hashed. Returns the User."""

    async def make(
        email: str = "user@example.com",
        *,
        role: Role = Role.user,
        is_active: bool = True,
        auth_method: AuthMethod = AuthMethod.password,
        password: str | None = "correct horse battery",
        **fields,
    ) -> User:
        user = User(
            email=email,
            role=role,
            is_active=is_active,
            auth_method=auth_method,
            password_hash=hash_password(password) if password else None,
            **fields,
        )
        db.add(user)
        await db.commit()
        return user

    return make
