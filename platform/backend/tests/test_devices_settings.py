import json

import httpx
import pytest
from sqlalchemy import select

from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.security import create_access_token
from app.devices.crypto import decrypt_token, encrypt_token
from app.devices.models import Device, DeviceCommand
from app.users.models import Role
from tests.fakeboard import ENTITIES, FakeBoard, error
from tests.helpers import auth

HOST = "10.1.3.50"


@pytest.fixture
async def device(db, lan):
    lan.add(HOST)
    row = Device(
        device_id="garage-abc123",
        type="garage",
        name="Garage",
        host=HOST,
        token_encrypted=encrypt_token("board-token-1"),
        entities=ENTITIES,
        online=True,
    )
    db.add(row)
    await db.commit()
    return row


@pytest.fixture
async def admin(make_user):
    user = await make_user("admin@example.com", role=Role.admin)
    return user, auth(create_access_token(user.id, "admin"))


async def fresh(pk) -> Device:
    async with get_sessionmaker()() as s:
        return await s.get(Device, pk)


async def audit() -> list[tuple[str, str, dict, str]]:
    async with get_sessionmaker()() as s:
        rows = await s.scalars(select(DeviceCommand).order_by(DeviceCommand.id))
        return [(r.entity, r.command, r.params, r.result) for r in rows]


ENDPOINTS = [
    ("get", "/api/devices/1/settings"),
    ("patch", "/api/devices/1/settings"),
    ("post", "/api/devices/1/restart"),
    ("post", "/api/devices/1/rotate-token"),
    ("get", "/api/devices/1/token"),
    ("patch", "/api/devices/1"),
]


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
async def test_only_admins(client, make_user, device, method, path):
    assert (await client.request(method, path, json={})).status_code == 401
    for role in (Role.none, Role.user):
        user = await make_user(f"{role}@example.com", role=role)
        headers = auth(create_access_token(user.id, role.value))
        assert (await client.request(method, path, json={}, headers=headers)).status_code == 403


# ---- settings ----


async def test_read_shows_only_the_driver_fields(client, device, admin):
    _, headers = admin

    body = (await client.get("/api/devices/1/settings", headers=headers)).json()

    assert body == {
        "name": "Garage",
        "open_s": 20,
        "close_s": 40,
        "light_s": 120,
        "night_level": 700,
        "display": True,
    }


async def test_a_change_sends_only_what_changed(client, lan, device, admin):
    _, headers = admin
    board = lan.boards[HOST]

    response = await client.patch(
        "/api/devices/1/settings", json={"light_s": 300, "open_s": 20}, headers=headers
    )

    assert response.status_code == 200
    assert response.json()["light_s"] == 300
    post = [r for r in board.requests if r.method == "POST"][-1]
    assert json.loads(post.content) == {"light_s": 300}
    assert board.settings["light_s"] == 300
    assert await audit() == [("settings", "update", {"light_s": 300}, "ok")]


async def test_nothing_changed_sends_nothing(client, lan, device, admin):
    _, headers = admin

    await client.patch("/api/devices/1/settings", json={"light_s": 120}, headers=headers)

    assert all(r.method == "GET" for r in lan.boards[HOST].requests)
    assert await audit() == []


async def test_a_new_name_is_raw_utf8_and_renames_the_device(client, lan, device, admin):
    _, headers = admin

    await client.patch("/api/devices/1/settings", json={"name": "Garaxe ñ"}, headers=headers)

    post = [r for r in lan.boards[HOST].requests if r.method == "POST"][-1]
    assert post.content == '{"name": "Garaxe ñ"}'.encode()
    assert (await fresh(device.id)).name == "Garaxe ñ"


async def test_the_name_is_counted_in_bytes(client, device, admin):
    _, headers = admin

    ok = await client.patch("/api/devices/1/settings", json={"name": "ñ" * 16}, headers=headers)
    too_long = await client.patch(
        "/api/devices/1/settings", json={"name": "ñ" * 17}, headers=headers
    )

    assert ok.status_code == 200
    assert too_long.status_code == 422
    assert too_long.json()["error"]["details"][0]["loc"] == ["body", "name"]


@pytest.mark.parametrize(
    "body",
    [
        {"open_s": 4},
        {"open_s": 101},
        {"close_s": 9},
        {"light_s": 601},
        {"night_level": 0},
        {"night_level": 1024},
        {"display": 1},
        {"open_s": "20"},
        {"name": ""},
        {"name": "a\nb"},
        {"wifi_ssid": "evil"},
        {"wifi_password": "12345678"},
        {"token": "abcdefgh"},
    ],
)
async def test_values_the_board_would_refuse_and_fields_it_never_gets(
    client, lan, device, admin, body
):
    _, headers = admin

    response = await client.patch("/api/devices/1/settings", json=body, headers=headers)

    assert response.status_code == 422
    assert lan.boards[HOST].requests == []


@pytest.mark.parametrize(
    ("answer", "status", "code"),
    [
        (error(400, "invalid_light_time"), 400, "invalid_light_time"),
        (error(500, "save_failed"), 502, "device_save_failed"),
        (error(401, "unauthorized"), 409, "device_token_invalid"),
        (error(503, "busy"), 502, "device_error"),
    ],
)
async def test_board_refusals(client, lan, device, admin, answer, status, code):
    _, headers = admin
    board = lan.boards[HOST]
    original = board.post_settings
    board.post_settings = lambda body: answer

    response = await client.patch("/api/devices/1/settings", json={"light_s": 300}, headers=headers)

    board.post_settings = original
    assert (response.status_code, response.json()["error"]["code"]) == (status, code)
    assert (await audit())[0][3] == answer.json()["error"]["code"]


async def test_an_answer_without_settings_keeps_what_was_asked(client, lan, device, admin):
    _, headers = admin
    board = lan.boards[HOST]
    board.post_settings = lambda body: httpx.Response(200, json={"result": "ok"})

    body = (
        await client.patch("/api/devices/1/settings", json={"light_s": 300}, headers=headers)
    ).json()

    assert body["light_s"] == 300


async def test_a_board_that_does_not_answer(client, lan, device, admin):
    _, headers = admin
    lan.boards[HOST].unreachable = True

    response = await client.get("/api/devices/1/settings", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (502, "device_unreachable")


async def test_an_unknown_type_has_no_settings(client, db, device, admin):
    _, headers = admin
    device.type = "sound"
    await db.commit()

    for method in ("get", "patch"):
        response = await client.request(method, "/api/devices/1/settings", json={}, headers=headers)
        assert (response.status_code, response.json()["error"]["code"]) == (
            404,
            "settings_not_supported",
        )


async def test_settings_of_an_unknown_device(client, admin):
    _, headers = admin

    response = await client.patch("/api/devices/9/settings", json={}, headers=headers)

    assert response.json()["error"]["code"] == "device_not_found"


# ---- restart ----


async def test_restart(client, lan, device, admin):
    _, headers = admin

    response = await client.post("/api/devices/1/restart", headers=headers)

    assert response.status_code == 204
    assert lan.boards[HOST].restarts == 1
    assert await audit() == [("device", "restart", {}, "ok")]


@pytest.mark.parametrize(
    ("answer", "status", "code"),
    [(error(409, "door_busy"), 409, "door_busy"), (error(500, "x"), 502, "device_error")],
)
async def test_restart_refused(client, lan, device, admin, answer, status, code):
    _, headers = admin
    lan.boards[HOST].raw["restart"] = answer

    response = await client.post("/api/devices/1/restart", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (status, code)
    assert (await audit())[0][:2] == ("device", "restart")


# ---- token ----


async def test_rotation_sets_confirms_and_stores_a_new_token(client, lan, device, admin):
    _, headers = admin
    board = lan.boards[HOST]

    response = await client.post("/api/devices/1/rotate-token", headers=headers)

    assert response.status_code == 204
    assert board.token not in (None, "board-token-1")
    assert decrypt_token((await fresh(device.id)).token_encrypted) == board.token
    set_it = next(r for r in board.requests if r.method == "POST")
    assert set_it.headers["Authorization"] == "Bearer board-token-1"
    assert await audit() == [("token", "rotate", {}, "ok")]
    assert board.token not in str(await audit())


async def test_rotation_refused_by_the_board_changes_nothing(client, lan, device, admin):
    _, headers = admin
    board = lan.boards[HOST]
    board.token = "someone-else-changed-it"

    response = await client.post("/api/devices/1/rotate-token", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (409, "device_token_invalid")
    assert decrypt_token((await fresh(device.id)).token_encrypted) == "board-token-1"


async def test_rotation_without_an_answer_but_taken_is_stored(client, lan, device, admin):
    _, headers = admin
    board = lan.boards[HOST]
    real = board.post_settings

    def take_then_drop(body):
        real(body)
        raise httpx.ReadTimeout("lost answer")

    board.post_settings = take_then_drop

    response = await client.post("/api/devices/1/rotate-token", headers=headers)

    assert response.status_code == 204
    assert decrypt_token((await fresh(device.id)).token_encrypted) == board.token != "board-token-1"


async def test_rotation_without_an_answer_and_not_taken_keeps_the_old_one(
    client, lan, device, admin
):
    _, headers = admin
    board = lan.boards[HOST]

    def drop(body):
        raise httpx.ReadTimeout("lost")

    board.post_settings = drop

    response = await client.post("/api/devices/1/rotate-token", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (502, "device_unreachable")
    assert decrypt_token((await fresh(device.id)).token_encrypted) == "board-token-1"


async def test_rotation_the_board_does_not_confirm(client, lan, device, admin):
    _, headers = admin
    board = lan.boards[HOST]
    board.failures["settings"] = (503, "busy")  # GET /settings fails after the POST
    real = board.answer

    def answer(request):
        if request.method == "POST":
            board.failures.pop("settings", None)
            response = real(request)
            board.failures["settings"] = (503, "busy")
            return response
        return real(request)

    board.answer = answer

    response = await client.post("/api/devices/1/rotate-token", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (
        502,
        "device_token_unconfirmed",
    )
    assert (await audit())[0][3] == "unconfirmed"
    # The board took the new token: it is stored, and the old one kept as the previous token.
    stored = await fresh(device.id)
    assert decrypt_token(stored.token_encrypted) == board.token != "board-token-1"
    assert decrypt_token(stored.token_previous_encrypted) == "board-token-1"
    revealed = (await client.get("/api/devices/1/token", headers=headers)).json()
    assert revealed == {"token": board.token, "previous_token": "board-token-1"}


async def test_reveal(client, device, admin):
    _, headers = admin

    response = await client.get("/api/devices/1/token", headers=headers)

    assert response.json() == {"token": "board-token-1", "previous_token": None}
    assert response.headers["Cache-Control"] == "no-store"
    assert await audit() == [("token", "reveal", {}, "ok")]


async def test_reveal_without_a_token(client, db, device, admin):
    _, headers = admin
    device.token_encrypted = None
    await db.commit()

    response = await client.get("/api/devices/1/token", headers=headers)

    assert (response.status_code, response.json()["error"]["code"]) == (404, "device_has_no_token")


async def test_token_actions_are_rate_limited(client, device, admin, monkeypatch):
    _, headers = admin
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    try:
        for _ in range(ratelimit.DEVICE_TOKEN_USER.limit):
            await client.get("/api/devices/1/token", headers=headers)
        response = await client.get("/api/devices/1/token", headers=headers)
    finally:
        get_settings.cache_clear()

    assert response.status_code == 429


# ---- host and token by hand ----


async def test_a_new_host_must_be_the_same_board(client, lan, device, admin):
    _, headers = admin
    lan.add("10.1.3.51")  # the same board (id garage-abc123) at its new address
    lan.add("10.1.3.52", FakeBoard(device_id="garage-ffffff"))

    moved = await client.patch("/api/devices/1", json={"host": "10.1.3.51"}, headers=headers)
    other = await client.patch("/api/devices/1", json={"host": "10.1.3.52"}, headers=headers)
    nobody = await client.patch("/api/devices/1", json={"host": "10.1.3.53"}, headers=headers)

    assert (moved.status_code, moved.json()["host"]) == (200, "10.1.3.51")
    assert (other.status_code, other.json()["error"]["code"]) == (409, "device_mismatch")
    assert nobody.json()["error"]["code"] == "device_unreachable"
    lan.boards["10.1.3.54"] = lan.boards["10.1.3.51"]
    lan.boards["10.1.3.54"].raw["info"] = httpx.Response(404, text="no")
    assert (
        await client.patch("/api/devices/1", json={"host": "10.1.3.54"}, headers=headers)
    ).json()["error"]["code"] == "not_a_device"


async def test_re_entering_the_token(client, lan, device, admin):
    _, headers = admin
    lan.boards[HOST].token = "the-board-now-says"

    wrong = await client.patch("/api/devices/1", json={"token": "a-wrong-token"}, headers=headers)
    right = await client.patch(
        "/api/devices/1", json={"token": "the-board-now-says"}, headers=headers
    )

    assert wrong.json()["error"]["code"] == "device_token_invalid"
    assert right.status_code == 200
    assert decrypt_token((await fresh(device.id)).token_encrypted) == "the-board-now-says"
    assert ("device", "update", {"host": HOST, "token": True}, "ok") in await audit()
    assert "the-board-now-says" not in str(await audit())


async def test_the_same_host_is_not_checked_again(client, lan, device, admin):
    _, headers = admin

    response = await client.patch("/api/devices/1", json={"host": HOST}, headers=headers)

    assert response.status_code == 200
    assert lan.boards[HOST].requests == []


async def test_an_answer_with_partial_settings_keeps_the_stored_name(client, lan, device, admin):
    _, headers = admin
    lan.boards[HOST].post_settings = lambda body: httpx.Response(
        200, json={"result": "ok", "settings": {"light_s": 300}}
    )

    body = (
        await client.patch("/api/devices/1/settings", json={"light_s": 300}, headers=headers)
    ).json()

    assert body == {"light_s": 300}
    assert (await fresh(device.id)).name == "Garage"


async def test_no_answer_at_all_keeps_both_tokens(client, lan, device, admin):
    _, headers = admin
    board = lan.boards[HOST]

    def take_then_vanish(body):
        board.token = body["token"]
        board.unreachable = True  # the board took it, then stopped answering
        raise httpx.ReadTimeout("lost")

    board.post_settings = take_then_vanish

    response = await client.post("/api/devices/1/rotate-token", headers=headers)

    assert response.json()["error"]["code"] == "device_token_unconfirmed"
    stored = await fresh(device.id)
    assert decrypt_token(stored.token_encrypted) == board.token
    assert decrypt_token(stored.token_previous_encrypted) == "board-token-1"


async def test_a_confirmed_rotation_or_a_re_entered_token_drops_the_previous_one(
    client, db, lan, device, admin
):
    _, headers = admin
    device.token_previous_encrypted = encrypt_token("an-older-token")
    await db.commit()

    await client.post("/api/devices/1/rotate-token", headers=headers)
    assert (await fresh(device.id)).token_previous_encrypted is None

    device = await fresh(device.id)
    async with get_sessionmaker()() as s:
        row = await s.get(Device, device.id)
        row.token_previous_encrypted = encrypt_token("an-older-token")
        await s.commit()
    await client.patch("/api/devices/1", json={"token": lan.boards[HOST].token}, headers=headers)
    assert (await fresh(device.id)).token_previous_encrypted is None


async def test_a_rotation_the_board_still_refuses_keeps_the_old_token(client, lan, device, admin):
    _, headers = admin
    board = lan.boards[HOST]
    board.post_settings = lambda body: httpx.Response(
        200, json={"result": "ok"}
    )  # says ok, keeps old

    response = await client.post("/api/devices/1/rotate-token", headers=headers)

    assert response.json()["error"]["code"] == "device_token_unchanged"
    stored = await fresh(device.id)
    assert (decrypt_token(stored.token_encrypted), stored.token_previous_encrypted) == (
        "board-token-1",
        None,
    )
    assert (await audit())[0][3] == "kept"


async def test_refused_updates_are_recorded(client, lan, device, admin):
    _, headers = admin
    lan.add("10.1.3.52", FakeBoard(device_id="garage-ffffff"))

    await client.patch("/api/devices/1", json={"host": "10.1.3.52"}, headers=headers)
    await client.patch("/api/devices/1", json={"token": "a-wrong-token"}, headers=headers)

    assert [row[3] for row in await audit()] == ["device_mismatch", "device_token_invalid"]
    assert (await fresh(device.id)).host == HOST


async def test_changing_the_host_is_rate_limited(client, lan, device, admin, monkeypatch):
    _, headers = admin
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    try:
        for _ in range(ratelimit.DEVICE_ADD_USER.limit):
            await client.patch("/api/devices/1", json={"host": "10.1.3.99"}, headers=headers)
        response = await client.patch("/api/devices/1", json={"host": "10.1.3.99"}, headers=headers)
    finally:
        get_settings.cache_clear()

    assert response.status_code == 429


async def test_two_unconfirmed_rotations_in_a_row_never_lose_the_board_s_token(
    client, lan, device, admin
):
    _, headers = admin
    board = lan.boards[HOST]

    def take_then_vanish(body):
        board.token = body["token"]
        board.unreachable = True
        raise httpx.ReadTimeout("lost")

    board.post_settings = take_then_vanish
    first = await client.post("/api/devices/1/rotate-token", headers=headers)
    on_board = board.token  # new1: stored, with the old one as previous
    posts = len([r for r in board.requests if r.method == "POST"])

    second = await client.post("/api/devices/1/rotate-token", headers=headers)  # still offline

    assert first.json()["error"]["code"] == "device_token_unconfirmed"
    assert second.json()["error"]["code"] == "device_unreachable"
    assert len([r for r in board.requests if r.method == "POST"]) == posts  # nothing sent
    stored = await fresh(device.id)
    assert decrypt_token(stored.token_encrypted) == on_board
    assert decrypt_token(stored.token_previous_encrypted) == "board-token-1"
    assert (await audit())[-1][3] == "unsettled"


async def test_a_command_settles_a_pending_token_on_the_one_the_board_has(
    client, db, lan, device, make_user
):
    # An unconfirmed rotation whose request never arrived: the board is still on the previous token.
    device.token_encrypted = encrypt_token("never-reached-the-board")
    device.token_previous_encrypted = encrypt_token("board-token-1")
    await db.commit()
    user = await make_user("ana@example.com", role=Role.user)

    response = await client.post(
        "/api/devices/1/entities/light/on", headers=auth(create_access_token(user.id, "user"))
    )

    assert response.status_code == 200
    stored = await fresh(device.id)
    assert (decrypt_token(stored.token_encrypted), stored.token_previous_encrypted) == (
        "board-token-1",
        None,
    )


async def test_reading_settings_settles_a_pending_token_on_the_current_one(
    client, db, lan, device, admin
):
    _, headers = admin
    device.token_previous_encrypted = encrypt_token("an-older-token")
    await db.commit()

    assert (await client.get("/api/devices/1/settings", headers=headers)).status_code == 200

    stored = await fresh(device.id)
    assert (decrypt_token(stored.token_encrypted), stored.token_previous_encrypted) == (
        "board-token-1",
        None,
    )


async def test_a_board_that_accepts_neither_keeps_both_until_it_answers(
    client, db, lan, device, admin
):
    _, headers = admin
    device.token_previous_encrypted = encrypt_token("an-older-token")
    await db.commit()
    lan.boards[HOST].unreachable = True

    response = await client.post("/api/devices/1/restart", headers=headers)

    assert response.json()["error"]["code"] == "device_unreachable"
    assert (await fresh(device.id)).token_previous_encrypted is not None
