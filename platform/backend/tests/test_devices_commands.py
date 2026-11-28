import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy import select

from app.core import ratelimit
from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.security import create_access_token
from app.devices.bus import StateChanged, bus
from app.devices.commands import attribute
from app.devices.crypto import encrypt_token
from app.devices.history import Log, collect, store_log
from app.devices.models import Device, DeviceCommand, DeviceEvent
from app.devices.poller import apply_state
from app.users.models import Role
from tests.fakeboard import ENTITIES, error, garage_state
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
        state=garage_state(rev=1),
        rev=1,
        online=True,
    )
    db.add(row)
    await db.commit()
    return row


@pytest.fixture
async def ana(make_user):
    user = await make_user("ana@example.com", role=Role.user, first_name="Ana")
    return user, auth(create_access_token(user.id, "user"))


async def send(client, headers, path, body=None, pk=1):
    return await client.post(f"/api/devices/{pk}/entities/{path}", json=body, headers=headers)


async def audit() -> list[DeviceCommand]:
    async with get_sessionmaker()() as fresh:
        return list(await fresh.scalars(select(DeviceCommand).order_by(DeviceCommand.id)))


async def stored_device(pk) -> Device:
    async with get_sessionmaker()() as fresh:
        return await fresh.get(Device, pk)


# ---- access ----


async def test_commands_need_a_user_role(client, make_user, device):
    assert (await send(client, {}, "door/open")).status_code == 401
    none = await make_user("none@example.com", role=Role.none)

    response = await send(client, auth(create_access_token(none.id, "none")), "door/open")

    assert response.status_code == 403
    assert await audit() == []


# ---- success ----


async def test_a_command_answers_the_new_state_and_saves_it(client, lan, device, ana):
    user, headers = ana
    events = bus.subscribe()

    response = await send(client, headers, "door/open")

    assert response.status_code == 200
    body = response.json()
    assert body["result"] == "ok"
    assert body["state"]["door"]["state"] == "opening"
    saved = await stored_device(device.id)
    assert (saved.rev, saved.state["door"]["state"]) == (2, "opening")
    assert events.get_nowait() == StateChanged(device.id, 2)
    request = lan.boards[HOST].requests[-1]
    assert (request.method, request.url.path) == ("POST", "/api/v1/door/open")
    assert request.headers["Authorization"] == "Bearer board-token-1"
    (row,) = await audit()
    assert (row.user_id, row.entity, row.command, row.params, row.result, row.status) == (
        user.id,
        "door",
        "open",
        {},
        "ok",
        200,
    )


async def test_the_light_takes_a_duration(client, lan, device, ana):
    _, headers = ana

    body = (await send(client, headers, "light/on", {"duration": 600})).json()

    assert body["state"]["light"] == {"state": "on", "timed": True, "remaining_s": 600}
    assert json.loads(lan.boards[HOST].requests[-1].content) == {"duration": 600}
    assert (await audit())[0].params == {"duration": 600}


async def test_without_a_body_nothing_is_sent(client, lan, device, ana):
    _, headers = ana

    await send(client, headers, "light/on")

    assert lan.boards[HOST].requests[-1].content == b""


async def test_a_noop_is_passed_through(client, lan, device, ana):
    _, headers = ana
    lan.boards[HOST].raw["door/close"] = httpx.Response(
        200, json={"result": "noop", "state": garage_state(rev=1)}
    )

    body = (await send(client, headers, "door/close")).json()

    assert body["result"] == "noop"
    assert (await audit())[0].result == "noop"


async def test_an_answer_without_a_state_keeps_the_stored_one(client, lan, device, ana):
    _, headers = ana
    lan.boards[HOST].raw["light/off"] = httpx.Response(200, json={"weird": True})

    body = (await send(client, headers, "light/off")).json()

    assert body == {"result": "ok", "state": garage_state(rev=1)}


async def test_an_older_state_never_replaces_a_newer_one():
    device = Device(rev=5, state=garage_state(rev=5, door="open"))

    assert apply_state(device, garage_state(rev=4, door="closed"), datetime.now(UTC)) is False

    assert device.state["door"]["state"] == "open"


# ---- refusals ----


@pytest.mark.parametrize(
    ("path", "code"),
    [
        ("fan/on", "entity_not_found"),
        ("door/explode", "command_not_found"),
        ("rssi/on", "command_not_found"),
    ],
)
async def test_unknown_entities_and_commands(client, lan, device, ana, path, code):
    _, headers = ana

    response = await send(client, headers, path)

    assert (response.status_code, response.json()["error"]["code"]) == (404, code)
    assert lan.boards[HOST].requests == []


async def test_an_unknown_device(client, ana):
    _, headers = ana

    response = await send(client, headers, "door/open", pk=99)

    assert response.json()["error"]["code"] == "device_not_found"


@pytest.mark.parametrize("path", ["Door/open", "door/op%20en", "door/" + "x" * 33])
async def test_malformed_paths(client, device, ana, path):
    _, headers = ana

    assert (await send(client, headers, path)).status_code == 422


async def test_parameters_only_where_the_command_takes_them(client, lan, device, ana):
    _, headers = ana

    response = await send(client, headers, "door/open", {"duration": 10})

    assert (response.status_code, response.json()["error"]["code"]) == (422, "invalid_params")
    assert lan.boards[HOST].requests == []


@pytest.mark.parametrize("duration", [-1, 86_401, "30", True, 1.5])
async def test_invalid_durations(client, device, ana, duration):
    _, headers = ana

    response = await send(client, headers, "light/on", {"duration": duration})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("answer", "status", "code", "recorded"),
    [
        (error(409, "door_busy"), 409, "door_busy", ("door_busy", 409)),
        (error(400, "invalid_duration"), 400, "invalid_duration", ("invalid_duration", 400)),
        (error(401, "unauthorized"), 409, "device_token_invalid", ("unauthorized", 401)),
        (error(500, "boom"), 502, "device_error", ("boom", 500)),
        (httpx.Response(500, text="oops"), 502, "device_error", ("device_error", 500)),
    ],
)
async def test_board_errors(client, lan, device, ana, answer, status, code, recorded):
    _, headers = ana
    lan.boards[HOST].raw["door/open"] = answer

    response = await send(client, headers, "door/open")

    assert (response.status_code, response.json()["error"]["code"]) == (status, code)
    row = (await audit())[0]
    assert (row.result, row.status) == recorded
    assert (await stored_device(device.id)).rev == 1


async def test_a_board_that_does_not_answer(client, lan, device, ana):
    _, headers = ana
    lan.boards[HOST].unreachable = True

    response = await send(client, headers, "door/open")

    assert (response.status_code, response.json()["error"]["code"]) == (502, "device_unreachable")
    assert ((await audit())[0].result, (await audit())[0].status) == ("device_unreachable", None)


async def test_an_offline_device_is_not_tried(client, db, lan, device, ana):
    _, headers = ana
    device.online = False
    await db.commit()

    response = await send(client, headers, "door/open")

    assert (response.status_code, response.json()["error"]["code"]) == (409, "device_offline")
    assert lan.boards[HOST].requests == []
    assert (await audit())[0].result == "device_offline"


async def test_a_stored_token_that_no_longer_decrypts(client, db, lan, device, ana):
    _, headers = ana
    device.token_encrypted = "not-fernet"
    await db.commit()

    response = await send(client, headers, "door/open")

    assert (response.status_code, response.json()["error"]["code"]) == (
        409,
        "device_token_unreadable",
    )
    assert (await audit())[0].result == "device_token_unreadable"


async def test_commands_are_rate_limited(client, device, ana, monkeypatch):
    _, headers = ana
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    try:
        for _ in range(ratelimit.COMMAND_USER.limit):
            await send(client, headers, "light/toggle")
        response = await send(client, headers, "light/toggle")
    finally:
        get_settings.cache_clear()

    assert response.status_code == 429


# ---- who caused which event ----

T0 = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


async def command(db, device, user, entity, cmd, at, result="ok"):
    db.add(
        DeviceCommand(
            device_pk=device.id,
            user_id=user.id if user else None,
            entity=entity,
            command=cmd,
            params={},
            at=at,
            result=result,
            status=200,
        )
    )
    await db.commit()


def ev(t, event, source="api", reason="command", value=0):
    return (t, event, source, reason, value)


async def history() -> list[tuple[str, str, int | None]]:
    async with get_sessionmaker()() as fresh:
        rows = await fresh.scalars(select(DeviceEvent).order_by(DeviceEvent.id))
        return [(r.event, r.source, r.user_id) for r in rows]


async def read(db, device, uptime, entries):
    # The board booted at T0 - 100 s; this read happens at its uptime `uptime`.
    now = T0 - timedelta(seconds=100) + timedelta(seconds=uptime)
    await store_log(db, device, Log(uptime, entries), now)


async def test_a_command_s_events_name_its_user(db, device, ana, make_user):
    user, _ = ana
    other = await make_user("bob@example.com", role=Role.user)
    await command(db, device, other, "door", "open", T0 - timedelta(seconds=40))  # too old
    await command(db, device, user, "door", "open", T0)
    await command(db, device, user, "light", "on", T0 + timedelta(seconds=60))

    await read(
        db,
        device,
        190,
        [
            ev(101, "door_opening"),
            ev(
                101, "light_on", source="auto", reason="none", value=120
            ),  # the auto light: nobody's
            ev(121, "door_open", reason="travel_end"),  # the movement's end: its start's user
            ev(160, "light_on", value=120),
        ],
    )

    assert await history() == [
        ("door_opening", "api", user.id),
        ("light_on", "auto", None),
        ("door_open", "api", user.id),
        ("light_on", "api", user.id),
    ]


async def test_a_failed_command_and_commands_from_elsewhere_name_nobody(db, device, ana):
    user, _ = ana
    await command(db, device, user, "door", "open", T0, result="door_busy")

    await read(
        db, device, 130, [ev(101, "door_opening"), ev(121, "door_open", reason="travel_end")]
    )

    assert await history() == [("door_opening", "api", None), ("door_open", "api", None)]


async def test_a_button_movement_names_nobody_even_after_a_command(db, device, ana):
    user, _ = ana
    await command(db, device, user, "door", "stop", T0)

    await read(
        db,
        device,
        160,
        [
            ev(101, "door_open", reason="stopped"),  # the stop command, right away
            ev(130, "door_closing", source="button"),
            ev(150, "door_closed", source="button", reason="sensor_closed"),
        ],
    )

    assert await history() == [
        ("door_open", "api", user.id),
        ("door_closing", "button", None),
        ("door_closed", "button", None),
    ]


async def test_a_movement_that_ends_in_the_next_read(db, device, ana):
    user, _ = ana
    await command(db, device, user, "door", "close", T0)

    await read(db, device, 105, [ev(101, "door_closing")])
    await read(
        db, device, 130, [ev(101, "door_closing"), ev(121, "door_closed", reason="sensor_closed")]
    )

    assert await history() == [("door_closing", "api", user.id), ("door_closed", "api", user.id)]


async def test_events_outside_a_device_family_are_left_alone(db, device):
    rows = [
        DeviceEvent(
            device_pk=device.id,
            boot_id=0,
            t=1,
            at=T0,
            event="wifi_up",
            source="api",
            reason="none",
            value=0,
        )
    ]

    await attribute(db, device.id, rows)
    await attribute(db, device.id, [])

    assert rows[0].user_id is None


async def test_commands_through_the_api_end_up_in_the_history(client, db, lan, device, ana):
    user, headers = ana
    board = lan.boards[HOST]
    await send(client, headers, "light/on")
    board.log = [{"t": 99, "event": "light_on", "source": "api", "reason": "none", "value": 120}]
    board.state = {**board.state, "uptime_s": 100}

    await collect(device.id)

    assert await history() == [("light_on", "api", user.id)]
    page = (await client.get("/api/events", headers=headers)).json()
    assert page["items"][0]["user"] == {"id": user.id, "name": "Ana"}


async def test_an_api_event_from_elsewhere_right_after_a_command_names_nobody(db, device, ana):
    user, _ = ana
    await command(db, device, user, "light", "on", T0)  # through the platform
    # One second later the board's own page switches the light off: no platform command.

    await read(
        db, device, 110, [ev(100, "light_on", reason="none"), ev(101, "light_off", reason="none")]
    )

    assert await history() == [("light_on", "api", user.id), ("light_off", "api", None)]


async def test_a_stop_from_elsewhere_after_an_open_names_nobody(db, device, ana):
    user, _ = ana
    await command(db, device, user, "door", "open", T0)

    await read(db, device, 110, [ev(100, "door_opening"), ev(103, "door_open", reason="stopped")])

    assert await history() == [("door_opening", "api", user.id), ("door_open", "api", None)]


async def test_a_reversal_is_three_events_of_one_command(db, device, ana):
    user, _ = ana
    await command(db, device, user, "door", "open", T0)  # stopped going up: close, stop, open

    await read(
        db,
        device,
        110,
        [
            ev(100, "door_closing"),
            ev(101, "door_open", reason="stopped"),
            ev(102, "door_opening"),
            ev(104, "door_open", reason="stopped"),  # then a stop from elsewhere
        ],
    )

    assert [u for _, _, u in await history()] == [user.id, user.id, user.id, None]


async def test_two_users_one_after_the_other(db, device, ana, make_user):
    user, _ = ana
    bob = await make_user("bob@example.com", role=Role.user)
    await command(db, device, user, "light", "on", T0)
    await command(db, device, bob, "light", "off", T0 + timedelta(seconds=1))

    await read(
        db, device, 110, [ev(100, "light_on", reason="none"), ev(101, "light_off", reason="none")]
    )

    assert [u for _, _, u in await history()] == [user.id, bob.id]


async def test_a_used_command_is_remembered_across_reads(db, device, ana):
    user, _ = ana
    await command(db, device, user, "light", "toggle", T0)

    await read(db, device, 105, [ev(100, "light_on", reason="none")])
    await read(
        db, device, 110, [ev(100, "light_on", reason="none"), ev(102, "light_off", reason="none")]
    )

    assert [u for _, _, u in await history()] == [user.id, None]
    (row,) = await audit()
    assert (row.credited, row.used) == (1, True)


async def test_a_command_never_credits_more_than_three_events(db, device, ana):
    user, _ = ana
    await command(db, device, user, "door", "open", T0)

    await read(
        db,
        device,
        110,
        [
            ev(100, "door_closing"),
            ev(101, "door_closing"),
            ev(102, "door_closing"),
            ev(103, "door_closing"),
        ],
    )

    assert [u for _, _, u in await history()] == [user.id] * 3 + [None]


async def test_a_pending_command_does_not_take_an_event_it_cannot_cause(db, device, ana):
    user, _ = ana
    await command(db, device, user, "light", "off", T0)

    await read(
        db, device, 110, [ev(100, "light_on", reason="none"), ev(101, "light_off", reason="none")]
    )

    assert [u for _, _, u in await history()] == [None, user.id]
