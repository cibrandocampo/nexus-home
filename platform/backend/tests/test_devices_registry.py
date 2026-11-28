import pytest
from sqlalchemy import select

from app.core import ratelimit
from app.core.config import get_settings
from app.core.security import create_access_token
from app.devices.crypto import decrypt_token
from app.devices.models import Device
from app.users.models import Role
from tests.fakeboard import FakeBoard, error
from tests.helpers import auth

HOST = "10.1.3.50"


@pytest.fixture
async def as_admin(make_user):
    admin = await make_user("admin@example.com", role=Role.admin)
    return auth(create_access_token(admin.id, "admin"))


@pytest.fixture
async def as_user(make_user):
    user = await make_user("user@example.com", role=Role.user)
    return auth(create_access_token(user.id, "user"))


@pytest.fixture
def board(lan):
    return lan.add(HOST)


async def add(client, headers, host=HOST, token="board-token-1"):
    body = {"host": host} if token is None else {"host": host, "token": token}
    return await client.post("/api/devices", json=body, headers=headers)


async def stored(db) -> Device:
    db.expire_all()
    return (await db.scalars(select(Device))).one()


# ---- access ----

ENDPOINTS = [
    ("get", "/api/devices"),
    ("post", "/api/devices"),
    ("get", "/api/devices/1"),
    ("delete", "/api/devices/1"),
]


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
async def test_every_endpoint_requires_authentication(client, method, path):
    assert (await client.request(method, path, json={})).status_code == 401


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
async def test_accounts_without_a_role_are_forbidden(client, make_user, method, path):
    user = await make_user("none@example.com", role=Role.none)
    headers = auth(create_access_token(user.id, "none"))

    response = await client.request(method, path, json={"host": HOST}, headers=headers)

    assert response.status_code == 403


@pytest.mark.parametrize(
    ("method", "path"), [("post", "/api/devices"), ("delete", "/api/devices/1")]
)
async def test_users_cannot_change_the_registry(client, as_user, method, path):
    response = await client.request(method, path, json={"host": HOST}, headers=as_user)

    assert response.status_code == 403


async def test_users_can_list_and_read_devices(client, board, as_admin, as_user):
    pk = (await add(client, as_admin)).json()["id"]

    assert (await client.get("/api/devices", headers=as_user)).json()["total"] == 1
    assert (await client.get(f"/api/devices/{pk}", headers=as_user)).status_code == 200


# ---- add ----


async def test_add_reads_the_board_and_stores_the_token_encrypted(client, db, board, as_admin):
    response = await add(client, as_admin)

    assert response.status_code == 201
    body = response.json()
    assert body["device_id"] == "garage-abc123"
    assert body["type"] == "garage"
    assert body["name"] == "Garage"
    assert body["sw_version"] == "2.0.6"
    assert body["host"] == HOST
    assert body["has_token"] is True
    assert body["online"] is True
    assert [e["id"] for e in body["entities"]][:2] == ["door", "light"]
    assert "token" not in body and "token_encrypted" not in body
    device = await stored(db)
    assert device.token_encrypted != "board-token-1"
    assert "board-token-1" not in device.token_encrypted
    assert decrypt_token(device.token_encrypted) == "board-token-1"


async def test_add_checks_the_token_with_an_authenticated_read(client, board, as_admin):
    await add(client, as_admin)

    checks = [r for r in board.requests if r.url.path == "/api/v1/settings"]
    assert checks[0].headers["Authorization"] == "Bearer board-token-1"


async def test_a_wrong_token_is_refused(client, db, board, as_admin):
    response = await add(client, as_admin, token="wrong-token")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "device_token_invalid"
    assert (await db.scalars(select(Device))).all() == []


async def test_a_board_without_a_token_gets_one(client, db, lan, as_admin):
    board = lan.add(HOST, FakeBoard(token=None))

    response = await add(client, as_admin, token=None)

    assert response.status_code == 201
    assert board.token is not None and 8 <= len(board.token) <= 64
    assert decrypt_token((await stored(db)).token_encrypted) == board.token
    set_token = next(r for r in board.requests if r.method == "POST")
    assert "Authorization" not in set_token.headers  # the board had no token to send


async def test_a_board_with_a_token_needs_it(client, board, as_admin):
    response = await add(client, as_admin, token=None)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "device_token_required"


async def test_a_board_that_cannot_save_the_new_token_is_not_added(client, db, lan, as_admin):
    board = lan.add(HOST, FakeBoard(token=None))
    board.failures["settings"] = (500, "save_failed")

    response = await add(client, as_admin, token=None)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "device_error"
    assert (await db.scalars(select(Device))).all() == []


async def test_an_address_that_does_not_answer(client, as_admin):
    response = await add(client, as_admin, host="10.1.3.99")

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "device_unreachable"


@pytest.mark.parametrize(
    "answer",
    [
        error(404, "not_found"),
        {"id": "garage-abc123", "api": "v2", "entities": []},
        {"id": "not a device id", "api": "v1", "entities": []},
        {"id": "garage-abc123", "api": "v1", "entities": "door"},
        {"id": "garage-abc123", "api": "v1", "entities": [{"type": "cover"}]},
    ],
)
async def test_something_else_at_the_address_is_not_a_device(client, board, as_admin, answer):
    import httpx

    board.raw["info"] = (
        answer if isinstance(answer, httpx.Response) else httpx.Response(200, json=answer)
    )

    response = await add(client, as_admin)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "not_a_device"


async def test_a_registered_device_cannot_be_added_twice(client, lan, board, as_admin):
    await add(client, as_admin)
    lan.add("10.1.3.51", FakeBoard())  # same id at another address

    response = await add(client, as_admin, host="10.1.3.51")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "device_exists"


async def test_a_board_error_on_the_token_check_is_reported(client, board, as_admin):
    board.failures["settings"] = (500, "internal")

    response = await add(client, as_admin)

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "device_error"


@pytest.mark.parametrize(
    "body",
    [
        {"host": ""},
        {"host": "http://10.1.3.50"},
        {"host": "10.1.3.50/api"},
        {"host": "-bad"},
        {"host": HOST, "token": "short"},
        {"host": HOST, "token": "has space in it"},
        {"host": HOST, "token": "x" * 65},
        {"host": HOST, "extra": 1},
    ],
)
async def test_invalid_add_bodies(client, as_admin, body):
    response = await client.post("/api/devices", json=body, headers=as_admin)

    assert response.status_code == 422


async def test_a_host_with_a_port_is_accepted(client, lan, as_admin):
    lan.add("sim-garage-a:8080")

    assert (await add(client, as_admin, host="sim-garage-a:8080")).status_code == 201


async def test_adding_is_rate_limited(client, lan, as_admin, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    try:
        for _ in range(ratelimit.DEVICE_ADD_USER.limit):
            await add(client, as_admin, host="10.1.3.99")
        response = await add(client, as_admin, host="10.1.3.99")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 429


# ---- list, read, delete ----


async def test_list_is_paginated_filtered_and_ordered_by_name(client, lan, as_admin):
    for i, name in enumerate(["Shed", "Garage", "Attic"]):
        lan.add(f"10.1.3.{60 + i}", FakeBoard(device_id=f"garage-00000{i}", name=name))
        await add(client, as_admin, host=f"10.1.3.{60 + i}")

    page = (await client.get("/api/devices?size=2", headers=as_admin)).json()
    assert [d["name"] for d in page["items"]] == ["Attic", "Garage"]
    assert (page["total"], page["page"], page["size"]) == (3, 1, 2)
    found = (await client.get("/api/devices?q=000001", headers=as_admin)).json()
    assert [d["name"] for d in found["items"]] == ["Garage"]
    assert (await client.get("/api/devices?q=she", headers=as_admin)).json()["total"] == 1


async def test_reading_an_unknown_device(client, as_admin):
    response = await client.get("/api/devices/99", headers=as_admin)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "device_not_found"


async def test_delete(client, board, as_admin):
    pk = (await add(client, as_admin)).json()["id"]

    assert (await client.delete(f"/api/devices/{pk}", headers=as_admin)).status_code == 204
    assert (await client.get(f"/api/devices/{pk}", headers=as_admin)).status_code == 404
    assert (await client.delete(f"/api/devices/{pk}", headers=as_admin)).status_code == 404


async def test_two_admins_adding_the_same_board_at_once(client, db, board, as_admin, monkeypatch):
    from app.core.db import get_sessionmaker
    from app.devices import service

    real_check = service.check_token

    async def check_then_race(host, token):
        await real_check(host, token)
        # Another request registers the same board between the existence check and the insert.
        async with get_sessionmaker()() as other:
            other.add(Device(device_id="garage-abc123", type="garage", name="x", host="10.9.9.9"))
            await other.commit()

    monkeypatch.setattr(service, "check_token", check_then_race)

    response = await add(client, as_admin)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "device_exists"
    assert (await stored(db)).host == "10.9.9.9"


async def test_two_adds_of_the_same_new_board_give_it_one_token(client, db, lan, as_admin):
    import asyncio

    board = lan.add(HOST, FakeBoard(token=None))
    board.delay_s = 0.02  # both requests read /info before either registers

    first, second = await asyncio.gather(
        add(client, as_admin, token=None), add(client, as_admin, token=None)
    )

    assert sorted([first.status_code, second.status_code]) == [201, 409]
    assert decrypt_token((await stored(db)).token_encrypted) == board.token
    assert len([r for r in board.requests if r.method == "POST"]) == 1
