"""Serves the built frontend: hashed assets cached forever, other non-API pages get index.html.

Unknown `/api/...` and `/assets/...` paths keep the JSON 404 envelope: only page navigations fall
back to the single-page app.
"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.types import Scope

IMMUTABLE = "public, max-age=31536000, immutable"
NO_CACHE = "no-cache"
NOT_SPA = ("/api/", "/assets/")


class ImmutableStaticFiles(StaticFiles):
    """File names under /assets carry a content hash, so a cached copy never goes stale."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        # Misses and wrong methods are raised as HTTPException; what returns is the file (200,
        # or 206 for a range) or a 304, and all of them keep the cache policy.
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = IMMUTABLE
        return response


def spa_response(request: Request, static_dir: Path) -> Response | None:
    """The SPA's answer for a path no route matched, or None when it must stay a 404."""
    path = request.url.path
    if request.method not in ("GET", "HEAD") or path == "/api" or path.startswith(NOT_SPA):
        return None
    # Top-level files from frontend/public (favicon, robots.txt…), never outside the directory.
    name = path.lstrip("/")
    # A NUL byte (`/%00`) makes every filesystem call raise: such a path is not a page.
    if "\x00" in path:
        return None
    if name and "/" not in name:
        candidate = (static_dir / name).resolve()
        if candidate.parent == static_dir.resolve() and candidate.is_file():
            return FileResponse(candidate, headers={"Cache-Control": NO_CACHE})
    return FileResponse(static_dir / "index.html", headers={"Cache-Control": NO_CACHE})


def mount_spa(app: FastAPI, static_dir: str) -> bool:
    """Serve the frontend when it has been built into `static_dir`; returns whether it was."""
    root = Path(static_dir)
    if not (root / "index.html").is_file():
        return False
    if (root / "assets").is_dir():
        app.mount("/assets", ImmutableStaticFiles(directory=root / "assets"), name="assets")
    app.state.spa_dir = root
    return True
