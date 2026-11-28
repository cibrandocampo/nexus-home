"""Application factory."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import health
from app.auth.router import router as auth_router
from app.core import scheduler
from app.core.config import ensure_production_ready, get_settings
from app.core.db import get_engine, get_sessionmaker
from app.core.errors import UnhandledErrorMiddleware, register_error_handlers
from app.core.headers import SecurityHeadersMiddleware
from app.core.logging import configure_logging
from app.devices import history, poller
from app.devices.router import events_router
from app.devices.router import router as devices_router
from app.spa import mount_spa
from app.users.bootstrap import ensure_admin
from app.users.router import router as users_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    async with get_sessionmaker()() as db:
        await ensure_admin(db)
    cleanup = scheduler.start()
    collecting = history.start()  # subscribes before the poller publishes
    polling = poller.start()
    yield
    await poller.stop(polling)
    await history.stop(collecting)
    await scheduler.stop(cleanup)
    # Close pooled database connections on shutdown.
    await get_engine().dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    ensure_production_ready(settings)
    configure_logging(settings.log_level)
    # The interactive docs load scripts from a CDN, which the CSP forbids: development only.
    docs = settings.env != "production"
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        docs_url="/api/docs" if docs else None,
        redoc_url=None,
        openapi_url="/api/openapi.json" if docs else None,
        lifespan=lifespan,
        # Behind the HTTPS proxy the app sees http: a slash redirect would send the browser to an
        # http:// URL. API paths are exact instead.
        redirect_slashes=False,
    )
    # The last one added is the outermost: even a 500 carries the security headers.
    app.add_middleware(UnhandledErrorMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    register_error_handlers(app)
    app.include_router(health.router, prefix="/api")
    app.include_router(auth_router, prefix="/api")
    app.include_router(users_router, prefix="/api")
    app.include_router(devices_router, prefix="/api")
    app.include_router(events_router, prefix="/api")
    mount_spa(app, settings.static_dir)
    return app


app = create_app()
