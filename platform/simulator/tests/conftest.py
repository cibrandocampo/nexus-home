import random

import pytest
from starlette.testclient import TestClient

from sim.app import make_app
from sim.device import Device, Identity
from sim.garage import Settings

TOKEN = "sim-token-1234"


class Clock:
    """A clock the tests move by hand: simulated seconds pass instantly."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


class Board:
    """A simulated board and an HTTP client for it, on a hand-moved clock."""

    def __init__(self, token: str = TOKEN, hooks: bool = True) -> None:
        self.clock = Clock()
        self.device = Device(
            Identity(id="garage-abc123", ip="10.0.0.9"),
            Settings(token=token),
            restart_s=2.0,
            now=self.clock,
            rng=random.Random(7),
        )
        self.client = TestClient(make_app(self.device, hooks=hooks, background=False))
        self.auth = {"Authorization": f"Bearer {token}"} if token else {}

    def wait(self, seconds: float) -> None:
        self.clock.t += seconds
        self.device.sync()

    def get(self, path: str, **kw):
        return self.client.get(f"/api/v1/{path}", **kw)

    def post(self, path: str, json=None, auth: bool = True, **kw):
        headers = {**(self.auth if auth else {}), **kw.pop("headers", {})}
        return self.client.post(f"/api/v1/{path}", json=json, headers=headers, **kw)

    def hook(self, name: str, json=None):
        return self.client.post(f"/sim/{name}", json=json)

    def state(self) -> dict:
        return self.get("state").json()

    def events(self) -> list[dict]:
        return self.get("log").json()["events"]

    def door(self) -> str:
        return self.state()["door"]["state"]


@pytest.fixture
def board() -> Board:
    return Board()
