"""Commands to the boards, their audit trail, and who caused which history event.

`POST /api/devices/{id}/entities/{entity}/{command}` sends `POST /api/v1/<entity>/<command>` with
the stored token. Every attempt is recorded in `DeviceCommand`, failures included. The board's log
only says `source: api`; the platform knows who sent the command, and `attribute` puts that user
on the events it caused.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.devices.bus import StateChanged, bus
from app.devices.client import DeviceError
from app.devices.models import Device, DeviceCommand, DeviceEvent
from app.devices.poller import apply_state
from app.devices.service import client_for, get_device
from app.users.models import User

log = logging.getLogger(__name__)

ENTITY_NOT_FOUND = AppError(404, "entity_not_found", "The device has no such entity")
COMMAND_NOT_FOUND = AppError(404, "command_not_found", "The entity has no such command")
OFFLINE = AppError(409, "device_offline", "The device is offline")
INVALID_PARAMS = AppError(422, "invalid_params", "This command takes no parameters")

# Board error codes passed through with their meaning (README "Errors"); any other → device_error.
PASS_THROUGH = {
    "door_busy": AppError(
        409, "door_busy", "The door is moving or was just triggered, retry later"
    ),
    "invalid_duration": AppError(400, "invalid_duration", "The duration is not valid"),
}
# Commands that take parameters, and which.
PARAMS = {("light", "on"): {"duration"}}

# An event the command caused right away is logged within a second or two of it (board times are
# whole seconds); a door movement's end belongs to the movement that started it.
IMMEDIATE_S = 5
ENDS = {"door_open", "door_closed", "close_failed"}
STARTS = {"door_opening", "door_closing"}
# What each command can cause right away, and the event that uses it up. A reversal (open a door
# stopped while opening, close one stopped while closing) is three pulses from one command: the
# wrong way, a stop, then the way asked.
DOOR_NOW = {"door_opening", "door_closing", "door_open", "door_closed"}
EXPECTS: dict[tuple[str, str], tuple[set[str], set[str]]] = {
    ("door", "open"): ({"door_closing", "door_open", "door_opening"}, {"door_opening"}),
    ("door", "close"): ({"door_opening", "door_closed", "door_closing"}, {"door_closing"}),
    ("door", "stop"): ({"door_open", "door_closed"}, {"door_open", "door_closed"}),
    ("door", "toggle"): (DOOR_NOW, DOOR_NOW),
    ("light", "on"): ({"light_on"}, {"light_on"}),
    ("light", "off"): ({"light_off"}, {"light_off"}),
    ("light", "toggle"): ({"light_on", "light_off"}, {"light_on", "light_off"}),
}
MAX_CREDITS = 3


def find_command(device: Device, entity: str, command: str) -> None:
    for e in device.entities:
        if e.get("id") == entity:
            if command not in (e.get("commands") or []):
                raise COMMAND_NOT_FOUND
            return
    raise ENTITY_NOT_FOUND


def _board_error(exc: DeviceError) -> AppError:
    if exc.status is None:
        return AppError(502, "device_unreachable", "The device did not answer")
    if exc.code == "unauthorized":
        return AppError(409, "device_token_invalid", "The device refused the stored token")
    return PASS_THROUGH.get(exc.code) or AppError(
        502, "device_error", f"The device answered {exc.status} {exc.code}"
    )


async def _record(db: AsyncSession, row: DeviceCommand, result: str, status: int | None) -> None:
    row.result, row.status = result, status
    db.add(row)
    await db.commit()


async def send(
    db: AsyncSession, device_pk: int, entity: str, command: str, params: dict[str, Any], user: User
) -> dict[str, Any]:
    device = await get_device(db, device_pk)
    find_command(device, entity, command)
    if set(params) - PARAMS.get((entity, command), set()):
        raise INVALID_PARAMS
    row = DeviceCommand(
        device_pk=device.id,
        user_id=user.id,
        entity=entity,
        command=command,
        params=params,
        at=datetime.now(UTC),
    )
    if not device.online:
        await _record(db, row, OFFLINE.code, None)
        raise OFFLINE
    try:
        answer = await client_for(device).post(f"{entity}/{command}", params or None)
    except DeviceError as exc:
        error = _board_error(exc)
        await _record(db, row, exc.code if exc.status else error.code, exc.status)
        log.info("Command %s/%s to device %s: %s", entity, command, device.device_id, error.code)
        raise error from None
    except AppError as exc:  # the stored token does not decrypt
        await _record(db, row, exc.code, None)
        raise
    result, state = answer.get("result"), answer.get("state")
    saved = isinstance(state, dict) and isinstance(state.get("rev"), int)
    changed = saved and apply_state(device, state, datetime.now(UTC))
    await _record(db, row, result if isinstance(result, str) else "ok", 200)
    if changed:  # after the audit row: the history reads the log now and credits this command
        bus.publish(StateChanged(device.id, state["rev"]))
    log.info("Command %s/%s to device %s: %s", entity, command, device.device_id, row.result)
    return {"result": row.result, "state": device.state}


def family(event: str) -> str | None:
    if event.startswith("door_") or event == "close_failed":
        return "door"
    if event.startswith("light_"):
        return "light"
    return None


async def attribute(db: AsyncSession, device_pk: int, events: list[DeviceEvent]) -> None:
    """Fill `user_id` on new `source: api` events (oldest first) from the platform's commands.

    - An event a command causes right away (the door starting or stopping, the light switching)
      takes the user of the oldest successful command on that entity, not yet used up, sent between
      IMMEDIATE_S before and 2 s after it (board times are whole seconds), and only if that command
      can cause that event (EXPECTS). Its target event uses the command up: one command names the
      events it caused, never a later one sent from elsewhere.
    - The end of a door movement (open at the end of the travel, closed by the sensor, close failed)
      takes the user of the movement's start.
    Commands from elsewhere (the board's own page, Home Assistant) find no command and stay null.
    """
    start_user: int | None = await _last_start_user(db, device_pk, events)
    for ev in events:
        fam = family(ev.event)
        if ev.source != "api" or fam is None:
            if ev.event in STARTS:
                start_user = None  # a button or a sensor started this movement
            continue
        if ev.event in ENDS and ev.reason != "stopped":
            ev.user_id = start_user
            continue
        ev.user_id = await _credit(db, device_pk, fam, ev)
        if ev.event in STARTS:
            start_user = ev.user_id


async def _credit(db: AsyncSession, device_pk: int, entity: str, ev: DeviceEvent) -> int | None:
    candidates = await db.scalars(
        select(DeviceCommand)
        .where(
            DeviceCommand.device_pk == device_pk,
            DeviceCommand.entity == entity,
            DeviceCommand.result == "ok",
            DeviceCommand.used.is_(False),
            DeviceCommand.at >= ev.at - timedelta(seconds=IMMEDIATE_S),
            DeviceCommand.at <= ev.at + timedelta(seconds=2),
        )
        .order_by(DeviceCommand.at, DeviceCommand.id)
    )
    for cmd in candidates:
        causes, target = EXPECTS.get((cmd.entity, cmd.command), (set(), set()))
        if ev.event in causes:
            cmd.credited += 1
            cmd.used = ev.event in target or cmd.credited >= MAX_CREDITS
            return cmd.user_id
    return None


async def _last_start_user(
    db: AsyncSession, device_pk: int, events: list[DeviceEvent]
) -> int | None:
    """The user of the stored movement start just before these (not yet added) events: a movement
    can begin in one read and end in the next."""
    if not events:
        return None
    return await db.scalar(
        select(DeviceEvent.user_id)
        .where(
            DeviceEvent.device_pk == device_pk,
            DeviceEvent.event.in_(STARTS),
            DeviceEvent.at <= events[0].at,
        )
        .order_by(DeviceEvent.at.desc(), DeviceEvent.id.desc())
        .limit(1)
    )
