from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.db import get_session


async def test_health_reports_ok_when_the_database_answers(client):
    response = await client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "dev"}


async def test_health_reports_503_when_the_database_is_unreachable(app, client):
    engine = create_async_engine(
        "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/none", poolclass=NullPool
    )

    async def unreachable_session():
        async with AsyncSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = unreachable_session

    response = await client.get("/api/health")

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
