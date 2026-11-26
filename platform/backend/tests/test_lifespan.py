from unittest.mock import AsyncMock, patch

from app.main import lifespan


async def test_startup_creates_the_admin_and_shutdown_disposes_the_engine(app):
    engine = AsyncMock()

    with (
        patch("app.main.get_engine", return_value=engine),
        patch("app.main.ensure_admin", new=AsyncMock()) as ensure_admin,
    ):
        async with lifespan(app):
            ensure_admin.assert_awaited_once()
            engine.dispose.assert_not_awaited()

    engine.dispose.assert_awaited_once()
