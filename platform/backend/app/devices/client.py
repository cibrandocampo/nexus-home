"""HTTP client for a board's `/api/v1` (README of each device, "API").

A board serves one connection at a time and closes it after each answer: every request to a host
goes through that host's lock, so polling, commands and settings never overlap on a board.
Bodies are sent as raw UTF-8: the boards refuse `\\u` escapes above 0x7F.
"""

import asyncio
import json
from typing import Any

import httpx

from app.core.config import get_settings

# Tests replace it with an httpx.MockTransport; None means the real network.
transport: httpx.AsyncBaseTransport | None = None

_locks: dict[str, asyncio.Lock] = {}


def host_lock(host: str) -> asyncio.Lock:
    lock = _locks.get(host)
    if lock is None:
        lock = _locks[host] = asyncio.Lock()
    return lock


def reset_locks() -> None:
    """Forget the per-host locks (they belong to one event loop; tests run one loop each)."""
    _locks.clear()


class DeviceError(Exception):
    """A board answered with an error, or did not answer.

    `status` is the board's HTTP status (None when it did not answer); `code` the board's own
    error code (`door_busy`, `unauthorized`, `invalid_name`, …) or `device_unreachable` /
    `device_bad_answer`.
    """

    def __init__(self, status: int | None, code: str, message: str = "") -> None:
        super().__init__(f"{code} ({status})")
        self.status = status
        self.code = code
        self.message = message


class DeviceClient:
    def __init__(self, host: str, token: str | None = None, *, timeout: float | None = None):
        self.host = host
        self.token = token
        self.timeout = timeout if timeout is not None else get_settings().device_timeout_s

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict | None = None,
        params: dict | None = None,
        auth: bool = False,
    ) -> dict[str, Any]:
        headers = {"Connection": "close"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        content = None
        if body is not None:
            content = json.dumps(body, ensure_ascii=False).encode()
            headers["Content-Type"] = "application/json"
        async with (
            host_lock(self.host),
            httpx.AsyncClient(
                transport=transport,
                timeout=self.timeout,
                follow_redirects=False,
                trust_env=False,  # never through an environment proxy: boards are on the LAN
            ) as client,
        ):
            try:
                response = await client.request(
                    method,
                    f"http://{self.host}/api/v1/{path}",
                    content=content,
                    params=params,
                    headers=headers,
                )
            except httpx.HTTPError:
                raise DeviceError(None, "device_unreachable", "The device did not answer") from None
        return _answer(response)

    async def info(self) -> dict[str, Any]:
        return await self.request("GET", "info")

    async def state(self) -> dict[str, Any]:
        return await self.request("GET", "state")

    async def log(self) -> dict[str, Any]:
        return await self.request("GET", "log")

    async def settings(self) -> dict[str, Any]:
        return await self.request("GET", "settings", auth=True)

    async def post(
        self, path: str, body: dict | None = None, params: dict | None = None
    ) -> dict[str, Any]:
        return await self.request("POST", path, body=body, params=params, auth=True)


def _answer(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
    except ValueError:
        data = None
    if response.is_success:
        if not isinstance(data, dict):
            raise DeviceError(response.status_code, "device_bad_answer", "Not a JSON object")
        return data
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict) and isinstance(error.get("code"), str):
        raise DeviceError(response.status_code, error["code"], str(error.get("message", "")))
    raise DeviceError(response.status_code, "device_error", "The device answered an error")
