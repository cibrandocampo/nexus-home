"""HTTP front of the simulated board, routed like http.cpp `handle()`: same paths, methods, order of
checks (method, origin, token) and error envelope. Test hooks live under /sim/ (a real board answers
404 there) and can be switched off with SIM_HOOKS=0.

Configuration (environment): SIM_ID (garage-<6 hex>), SIM_TOKEN (empty = no token, as a new board),
SIM_NAME, SIM_VERSION, SIM_SPEED (simulated seconds per real second), SIM_LIGHT_LEVEL, SIM_IP,
SIM_RESTART_S, SIM_HOOKS.
"""

import asyncio
import contextlib
import json
import os
import socket

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from sim.device import Device, DeviceError, Identity
from sim.garage import Settings

SYNC_EVERY_S = 0.05


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def answer(status: int, body: dict) -> JSONResponse:
    return JSONResponse(body, status_code=status, headers={"Cache-Control": "no-store"})


def default_ip() -> str:
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def device_from_env(env: os._Environ | dict = os.environ) -> Device:
    identity = Identity(
        id=env.get("SIM_ID", "garage-5e1a00"),
        version=env.get("SIM_VERSION", "2.0.5"),
        ip=env.get("SIM_IP") or default_ip(),
    )
    device = Device(
        identity,
        Settings(name=env.get("SIM_NAME", "Garage"), token=env.get("SIM_TOKEN", "")),
        speed=float(env.get("SIM_SPEED", "1")),
        restart_s=float(env.get("SIM_RESTART_S", "2")),
    )
    device.garage.base_light_level = int(env.get("SIM_LIGHT_LEVEL", "400"))
    return device


def parse_body(raw: bytes) -> dict | None:
    """The JSON object of the body, {} when there is none, None when it is not a JSON object."""
    if not raw.strip():
        return {}
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def make_app(device: Device, hooks: bool = True, background: bool = True) -> Starlette:
    async def api(request: Request) -> Response:
        if wait := device.down_for():  # restarting or offline: the board does not answer
            await asyncio.sleep(wait)
        device.sync()
        try:
            return await dispatch(request)
        except DeviceError as e:
            return error(e.status, e.code, e.message)

    async def dispatch(request: Request) -> Response:
        method = request.method
        path = request.url.path
        if path == "/":
            if method != "GET":
                return error(405, "method_not_allowed", "Use GET")
            return Response(
                "<!doctype html><title>Simulated garage</title>", media_type="text/html"
            )
        if not path.startswith("/api/v1/"):
            return error(404, "not_found", "Not found")
        path = path[len("/api/v1/") :]
        get, post = method == "GET", method == "POST"
        auth = request.headers.get("authorization")

        if path == "info":
            return (
                answer(200, device.info()) if get else error(405, "method_not_allowed", "Use GET")
            )
        if path == "settings" and get:
            if not device.authorized(auth):
                return error(401, "unauthorized", "Missing or invalid bearer token")
            return answer(200, device.settings_json())
        if path in ("state", "log"):
            if not get:
                return error(405, "method_not_allowed", "Use GET")
            return answer(200, device.state() if path == "state" else device.garage.log_json())
        if not post:
            return error(405, "method_not_allowed", "Use POST")
        origin = request.headers.get("origin")
        if origin is not None and origin != f"http://{request.headers.get('host', '')}":
            return error(403, "forbidden", "Cross-origin request rejected")
        if not device.authorized(auth):
            return error(401, "unauthorized", "Missing or invalid bearer token")
        payload = parse_body(await request.body())
        if path == "settings":
            if payload is None:
                return error(400, "invalid_json", "Malformed field in the request body")
            return answer(200, device.change_settings(payload))
        if path == "restart":
            return answer(200, device.restart())
        if path == "firmware":
            return error(501, "not_simulated", "Firmware updates are not simulated yet")
        duration = request.query_params.get("duration")
        return answer(200, device.command(path, duration, payload or {}))

    async def hook(request: Request) -> Response:
        if request.method != "POST":
            if request.url.path == "/sim/status":
                device.sync()
                o = device.garage.opener
                return JSONResponse(
                    {
                        "position": round(o.position, 3),
                        "motion": o.motion,
                        "obstructed": o.obstructed,
                        "uptime_s": device.garage.uptime_s,
                        "speed": device.speed,
                    }
                )
            return error(405, "method_not_allowed", "Use POST")
        device.sync()
        body = parse_body(await request.body()) or {}
        name = request.url.path[len("/sim/") :]
        g = device.garage
        if name == "button":
            g.press_button()
        elif name == "door":  # moved by hand: the opener did not do it
            g.opener.position = min(1.0, max(0.0, float(body.get("position", 0))))
            g.opener.motion = 0
        elif name == "obstruct":
            g.opener.obstructed = bool(body.get("on", True))
        elif name == "light_level":
            g.base_light_level = int(body.get("level", g.base_light_level))
        elif name == "offline":
            device.go_offline(float(body.get("seconds", 10)))
        elif name == "fail_next_save":
            device.fail_next_save = True
        elif name == "power_cycle":
            device.power_cycle()
        else:
            return error(404, "not_found", "Unknown hook")
        return JSONResponse({"result": "ok"})

    @contextlib.asynccontextmanager
    async def lifespan(_app: Starlette):
        task = None
        if background:

            async def run() -> None:
                while True:
                    await asyncio.sleep(SYNC_EVERY_S)
                    device.sync()

            task = asyncio.create_task(run())
        yield
        if task:
            task.cancel()

    methods = ["GET", "POST", "PUT", "PATCH", "DELETE"]
    routes = []
    if hooks:
        routes.append(Route("/sim/{name}", hook, methods=methods))
    routes.append(Route("/{path:path}", api, methods=methods))
    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.device = device
    return app


def create_app() -> Starlette:
    """Entry point for uvicorn (`--factory sim.app:create_app`)."""
    return make_app(device_from_env(), hooks=os.environ.get("SIM_HOOKS", "1") != "0")
