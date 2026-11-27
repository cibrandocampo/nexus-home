"""A programmable stand-in for a board's /api/v1, served through httpx.MockTransport.

The real simulator (platform/simulator) runs in its own container for the dev stack and the
end-to-end suite; backend tests need a board they can script per test (answers, failures,
timeouts) without the network.
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any

import httpx

ENTITIES = [
    {
        "id": "door",
        "type": "cover",
        "device_class": "garage",
        "state": "door.state",
        "commands": ["open", "close", "stop", "toggle"],
    },
    {"id": "light", "type": "light", "state": "light.state", "commands": ["on", "off", "toggle"]},
    {
        "id": "door_problem",
        "type": "binary_sensor",
        "device_class": "problem",
        "state": "door.close_failed",
    },
    {"id": "night", "type": "binary_sensor", "state": "night"},
    {"id": "light_level", "type": "sensor", "state": "light_level"},
    {
        "id": "rssi",
        "type": "sensor",
        "device_class": "signal_strength",
        "unit": "dBm",
        "state": "wifi.rssi",
    },
]


COMMANDS = {f"{e['id']}/{c}" for e in ENTITIES for c in e.get("commands", [])}


def garage_state(rev: int = 1, uptime_s: int = 100, door: str = "closed") -> dict[str, Any]:
    return {
        "rev": rev,
        "uptime_s": uptime_s,
        "door": {
            "state": door,
            "moving": door in ("opening", "closing"),
            "sensor_closed": door == "closed",
            "close_failed": False,
            "stopped": "none",
            "since_s": 10,
            "last_source": "none",
        },
        "light": {"state": "off", "timed": False, "remaining_s": 0},
        "night": False,
        "light_level": 400,
        "button": False,
        "display": True,
        "wifi": {"ip": "10.1.3.50", "rssi": -60},
    }


@dataclass
class FakeBoard:
    device_id: str = "garage-abc123"
    name: str = "Garage"
    token: str | None = "board-token-1"
    sw_version: str = "2.0.6"
    state: dict[str, Any] = field(default_factory=garage_state)
    log: list[dict[str, Any]] = field(default_factory=list)
    settings: dict[str, Any] = field(
        default_factory=lambda: {
            "name": "Garage",
            "wifi_ssid": "home",
            "wifi_password_set": True,
            "token_set": True,
            "open_s": 20,
            "close_s": 40,
            "light_s": 120,
            "night_level": 700,
            "display": True,
            "stored": True,
            "wifi_trying": False,
        }
    )
    # path ("settings", "door/open", …) → (status, code): the next requests to it fail.
    failures: dict[str, tuple[int, str]] = field(default_factory=dict)
    # Raw answers instead of the normal one: path → httpx.Response.
    raw: dict[str, httpx.Response] = field(default_factory=dict)
    unreachable: bool = False
    delay_s: float = 0.0
    requests: list[httpx.Request] = field(default_factory=list)
    in_flight: int = 0
    max_in_flight: int = 0

    def info(self) -> dict[str, Any]:
        return {
            "id": self.device_id,
            "name": self.name,
            "mode": "normal",
            "manufacturer": "nexusHome",
            "model": "Garage IoT Controller (UNO R4 WiFi)",
            "sw_version": self.sw_version,
            "modem_fw": "0.6.0",
            "reset_reason": "pin",
            "api": "v1",
            "mac": "B4:3A:45:AB:C1:23",
            "hostname": self.device_id,
            "auth": self.token is not None,
            "entities": ENTITIES,
        }

    def authorised(self, request: httpx.Request) -> bool:
        return self.token is None or request.headers.get("Authorization") == f"Bearer {self.token}"

    async def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if self.delay_s:
                await asyncio.sleep(self.delay_s)
            if self.unreachable:
                raise httpx.ConnectTimeout("timed out", request=request)
            return self.answer(request)
        finally:
            self.in_flight -= 1

    def answer(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path.removeprefix("/api/v1/")
        if path in self.raw:
            return self.raw[path]
        if path in self.failures:
            status, code = self.failures[path]
            return error(status, code)
        needs_auth = request.method == "POST" or path == "settings"
        if needs_auth and not self.authorised(request):
            return error(401, "unauthorized")
        if request.method == "GET":
            body = {
                "info": self.info,
                "state": lambda: self.state,
                "log": lambda: {"uptime_s": self.state["uptime_s"], "events": self.log},
                "settings": lambda: self.settings,
            }.get(path)
            return httpx.Response(200, json=body()) if body else error(404, "not_found")
        if path == "settings":
            return self.post_settings(json.loads(request.content or b"{}"))
        if path in COMMANDS:
            return self.command(path, json.loads(request.content or b"{}"))
        return error(404, "not_found")

    def command(self, path: str, body: dict[str, Any]) -> httpx.Response:
        """Enough of the door and light for the platform: the new state, `rev` + 1."""
        state = json.loads(json.dumps(self.state))
        door, light = state["door"], state["light"]
        if path == "door/open":
            door.update(state="opening", moving=True, sensor_closed=False, last_source="api")
        elif path == "door/close":
            door.update(state="closing", moving=True, last_source="api")
        elif path == "light/on":
            seconds = body.get("duration", 120)
            light.update(state="on", timed=seconds > 0, remaining_s=seconds)
        elif path == "light/off":
            light.update(state="off", timed=False, remaining_s=0)
        state["rev"] += 1
        self.state = state
        return httpx.Response(200, json={"result": "ok", "state": state})

    def post_settings(self, body: dict[str, Any]) -> httpx.Response:
        if "token" in body:
            self.token = body["token"] or None
            self.settings["token_set"] = self.token is not None
        for key in ("name", "open_s", "close_s", "light_s", "night_level", "display"):
            if key in body:
                self.settings[key] = body[key]
        if "name" in body:
            self.name = body["name"]
        return httpx.Response(200, json={"result": "ok", "settings": self.settings})


def error(status: int, code: str) -> httpx.Response:
    return httpx.Response(status, json={"error": {"code": code, "message": code}})


class Lan:
    """Boards by host; any other host does not answer."""

    def __init__(self) -> None:
        self.boards: dict[str, FakeBoard] = {}
        self.in_flight = 0
        self.max_in_flight = 0  # across every board: shows whether two boards overlap

    def add(self, host: str, board: FakeBoard | None = None) -> FakeBoard:
        board = board or FakeBoard()
        self.boards[host] = board
        return board

    async def handle(self, request: httpx.Request) -> httpx.Response:
        board = self.boards.get(request.url.netloc.decode())
        if board is None:
            raise httpx.ConnectTimeout("no route", request=request)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            return await board.handle(request)
        finally:
            self.in_flight -= 1

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)
