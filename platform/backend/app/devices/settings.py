"""A board's stored settings, restart and token, for admins.

Only the driver's fields are read and written (never the WiFi network, never the token through the
settings form). Every change is recorded in `DeviceCommand` like a command, without secrets.
"""

import functools
import logging
import secrets
from datetime import UTC, datetime
from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, create_model
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.types import PLAIN_TEXT
from app.devices.client import DeviceClient, DeviceError
from app.devices.crypto import decrypt_token, encrypt_token
from app.devices.drivers import DRIVERS, Driver, driver_for
from app.devices.models import Device, DeviceCommand
from app.devices.service import (
    NOT_A_DEVICE,
    UNREACHABLE,
    accepts,
    check_info,
    check_token,
    client_for,
    device_error,
    device_token,
    get_device,
    settle_token,
)
from app.users.models import User

log = logging.getLogger(__name__)

NOT_SUPPORTED = AppError(404, "settings_not_supported", "This device type has no settings form")
SAVE_FAILED = AppError(502, "device_save_failed", "The device could not store its settings")
UNCONFIRMED = AppError(
    502, "device_token_unconfirmed", "The device did not confirm the new token: check it"
)
OTHER_DEVICE = AppError(409, "device_mismatch", "Another device answers at this address")
NO_TOKEN = AppError(404, "device_has_no_token", "This device has no stored token")
UNCHANGED = AppError(502, "device_token_unchanged", "The device answered but kept its old token")


def _bytes(limit: int):
    def check(value: str) -> str:
        if len(value.encode()) > limit:  # the board counts bytes: 16 "ñ" fit in 32, 17 do not
            raise ValueError(f"at most {limit} bytes")
        return value

    return check


def settings_model(driver: Driver) -> type[BaseModel]:
    """The PATCH body for a driver: its fields, optional, with the board's ranges."""
    return _settings_model(driver.type)


@functools.cache
def _settings_model(device_type: str) -> type[BaseModel]:
    driver = DRIVERS[device_type]
    fields: dict[str, Any] = {}
    for name, limit in driver.text_fields.items():
        text = Annotated[
            str,
            StringConstraints(strip_whitespace=True, min_length=1, pattern=PLAIN_TEXT),
            AfterValidator(_bytes(limit)),
        ]
        fields[name] = (text | None, None)
    for f in driver.int_fields:
        fields[f.name] = (int | None, Field(default=None, ge=f.min, le=f.max, strict=True))
    for name in driver.bool_fields:
        fields[name] = (bool | None, Field(default=None, strict=True))
    return create_model(
        f"{driver.type.title()}Settings", __config__=ConfigDict(extra="forbid"), **fields
    )


def driver_of(device: Device) -> Driver:
    driver = driver_for(device.type)
    if driver is None:
        raise NOT_SUPPORTED
    return driver


def _only(driver: Driver, settings: dict[str, Any]) -> dict[str, Any]:
    return {k: settings[k] for k in driver.settings_fields if k in settings}


def _record(db: AsyncSession, device: Device, user: User, entity: str, command: str, **kw) -> None:
    db.add(
        DeviceCommand(
            device_pk=device.id,
            user_id=user.id,
            entity=entity,
            command=command,
            params=kw.get("params", {}),
            at=datetime.now(UTC),
            result=kw.get("result", "ok"),
            status=kw.get("status", 200),
            used=True,  # never credited to history events
        )
    )


def _settings_error(exc: DeviceError) -> AppError:
    if exc.code.startswith("invalid_") and exc.status == 400:
        return AppError(400, exc.code, "The device refused this value")
    if exc.code == "save_failed":
        return SAVE_FAILED
    return device_error(exc)


async def read_settings(db: AsyncSession, device_pk: int) -> dict[str, Any]:
    device = await get_device(db, device_pk)
    await settle_token(db, device)
    driver = driver_of(device)
    try:
        return _only(driver, await client_for(device).settings())
    except DeviceError as exc:
        raise device_error(exc) from None


async def change_settings(
    db: AsyncSession, device_pk: int, body: BaseModel, user: User
) -> dict[str, Any]:
    device = await get_device(db, device_pk)
    driver = driver_of(device)
    wanted = body.model_dump(exclude_none=True)
    current = await read_settings(db, device_pk)
    changes = {k: v for k, v in wanted.items() if current.get(k) != v}
    if not changes:
        return current
    try:
        answer = await client_for(device).post("settings", changes)
    except DeviceError as exc:
        error = _settings_error(exc)
        _record(
            db,
            device,
            user,
            "settings",
            "update",
            params=changes,
            result=exc.code,
            status=exc.status,
        )
        await db.commit()
        raise error from None
    stored = answer.get("settings")
    settings = _only(driver, stored) if isinstance(stored, dict) else {**current, **changes}
    if isinstance(settings.get("name"), str):
        device.name = settings["name"][:64]
    _record(db, device, user, "settings", "update", params=changes)
    await db.commit()
    log.info("Changed settings %s of device %s", sorted(changes), device.device_id)
    return settings


async def restart(db: AsyncSession, device_pk: int, user: User) -> None:
    device = await get_device(db, device_pk)
    await settle_token(db, device)
    try:
        await client_for(device).post("restart")
    except DeviceError as exc:
        _record(db, device, user, "device", "restart", result=exc.code, status=exc.status)
        await db.commit()
        if exc.code == "door_busy":
            raise AppError(409, "door_busy", "The door is moving: restart when it stops") from None
        raise device_error(exc) from None
    _record(db, device, user, "device", "restart")
    await db.commit()
    log.info("Restarted device %s", device.device_id)


async def rotate_token(db: AsyncSession, device_pk: int, user: User) -> None:
    """Set a new random token on the board, confirm it, store it.

    The board decides: the token it accepts afterwards is stored. If it accepts neither (it took the
    request and then stopped answering, or never got it), the new token is stored and the old one
    kept as the previous token: the admin sees both, so the board is never left on a token nobody
    knows.
    """
    device = await get_device(db, device_pk)
    if not await settle_token(db, device):  # never pile a third token on two unsettled ones
        _record(db, device, user, "token", "rotate", result="unsettled", status=None)
        await db.commit()
        raise UNREACHABLE
    old = device_token(device)
    new = secrets.token_urlsafe(24)
    lost = False
    try:
        await DeviceClient(device.host, old).post("settings", {"token": new})
    except DeviceError as exc:
        lost = exc.status is None
        if not lost:  # the board refused it: nothing changed
            _record(db, device, user, "token", "rotate", result=exc.code, status=exc.status)
            await db.commit()
            raise device_error(exc) from None
    if await accepts(device.host, new):
        device.token_encrypted, device.token_previous_encrypted = encrypt_token(new), None
        _record(db, device, user, "token", "rotate")
        await db.commit()
        log.info("Rotated the token of device %s", device.device_id)
        return
    if old is not None and await accepts(device.host, old):
        _record(db, device, user, "token", "rotate", result="kept", status=None)
        await db.commit()
        raise (UNREACHABLE if lost else UNCHANGED)  # still on the old token, which stays stored
    device.token_encrypted = encrypt_token(new)
    device.token_previous_encrypted = encrypt_token(old) if old is not None else None
    _record(db, device, user, "token", "rotate", result="unconfirmed", status=None)
    await db.commit()
    log.warning("Token rotation of device %s not confirmed: both tokens kept", device.device_id)
    raise UNCONFIRMED


async def reveal_token(db: AsyncSession, device_pk: int, user: User) -> dict[str, str | None]:
    device = await get_device(db, device_pk)
    token = device_token(device)
    if token is None:
        raise NO_TOKEN
    previous = (
        decrypt_token(device.token_previous_encrypted) if device.token_previous_encrypted else None
    )
    _record(db, device, user, "token", "reveal")  # who saw it, never the token itself
    await db.commit()
    log.info("Token of device %s revealed to user %s", device.device_id, user.id)
    return {"token": token, "previous_token": previous}


async def _new_host(device: Device, host: str) -> None:
    try:
        info = check_info(await DeviceClient(host).info())
    except DeviceError as exc:
        raise (UNREACHABLE if exc.status is None else NOT_A_DEVICE) from None
    if info["id"] != device.device_id:
        raise OTHER_DEVICE


async def update_device(
    db: AsyncSession, device_pk: int, host: str | None, token: str | None, user: User
) -> Device:
    """Fix a wrong host (it must answer as this same device) or re-enter the token. Refusals are
    recorded too."""
    device = await get_device(db, device_pk)
    new_host = host or device.host
    params = {"host": new_host, "token": token is not None}
    try:
        if new_host != device.host:
            await _new_host(device, new_host)
        if token is not None:
            await check_token(new_host, token)
    except AppError as exc:  # nothing was changed yet
        _record(db, device, user, "device", "update", params=params, result=exc.code, status=None)
        await db.commit()
        raise
    if token is not None:
        device.token_encrypted, device.token_previous_encrypted = encrypt_token(token), None
    device.host = new_host
    _record(db, device, user, "device", "update", params=params)
    await db.commit()
    return device
