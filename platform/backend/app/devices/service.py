"""Device registry rules shared by the endpoints."""

import logging
import re
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.devices.client import DeviceClient, DeviceError, host_lock
from app.devices.crypto import decrypt_token, encrypt_token
from app.devices.drivers import device_type
from app.devices.models import Device

log = logging.getLogger(__name__)

DEVICE_NOT_FOUND = AppError(404, "device_not_found", "Device not found")
DEVICE_EXISTS = AppError(409, "device_exists", "This device is already registered")
UNREACHABLE = AppError(502, "device_unreachable", "The device did not answer")
NOT_A_DEVICE = AppError(422, "not_a_device", "No nexusHome device API at this address")
TOKEN_INVALID = AppError(400, "device_token_invalid", "The device refused this token")
TOKEN_REQUIRED = AppError(400, "device_token_required", "This device has a token: enter it")

# `<type>-<id>`: lower-case letters and digits, as the boards build it (`garage-3562d4`).
DEVICE_ID = re.compile(r"^[a-z][a-z0-9]{0,30}-[0-9a-z]{1,32}$")


def device_error(exc: DeviceError) -> AppError:
    """A board failure as the platform reports it (no board error code leaks unmapped)."""
    if exc.status is None:
        return UNREACHABLE
    if exc.code == "unauthorized":
        return AppError(409, "device_token_invalid", "The device refused the stored token")
    return AppError(502, "device_error", f"The device answered {exc.status} {exc.code}")


def check_info(info: dict[str, Any]) -> dict[str, Any]:
    """The `/info` answer of a nexusHome board, or `not_a_device`."""
    device_id = info.get("id")
    entities = info.get("entities")
    if (
        info.get("api") != "v1"
        or not isinstance(device_id, str)
        or not DEVICE_ID.match(device_id)
        or not isinstance(entities, list)
        or not all(isinstance(e, dict) and isinstance(e.get("id"), str) for e in entities)
    ):
        raise NOT_A_DEVICE
    return info


def _text(info: dict[str, Any], key: str, limit: int) -> str:
    value = info.get(key)
    return value[:limit] if isinstance(value, str) else ""


def apply_info(device: Device, info: dict[str, Any]) -> None:
    """Copy what `/info` says about the board onto its row."""
    device.name = _text(info, "name", 64) or device.device_id
    device.model = _text(info, "model", 128)
    device.sw_version = _text(info, "sw_version", 32)
    device.modem_fw = _text(info, "modem_fw", 32)
    device.mode = _text(info, "mode", 16)
    device.reset_reason = _text(info, "reset_reason", 32)
    device.mac = _text(info, "mac", 17)
    device.entities = info["entities"]


def device_token(device: Device) -> str | None:
    return decrypt_token(device.token_encrypted) if device.token_encrypted else None


def client_for(device: Device) -> DeviceClient:
    return DeviceClient(device.host, device_token(device))


async def list_devices(
    db: AsyncSession, *, q: str | None, page: int, size: int
) -> tuple[list[Device], int]:
    query = select(Device)
    if q and q.strip():
        term = q.strip()
        query = query.where(
            or_(
                Device.name.icontains(term, autoescape=True),
                Device.device_id.icontains(term, autoescape=True),
            )
        )
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(
        query.order_by(Device.name, Device.id).offset((page - 1) * size).limit(size)
    )
    return list(rows), total or 0


async def get_device(db: AsyncSession, pk: int) -> Device:
    device = await db.get(Device, pk)
    if device is None:
        raise DEVICE_NOT_FOUND
    return device


async def check_token(host: str, token: str) -> None:
    """An authenticated read: the board accepts `token`, or `device_token_invalid`."""
    try:
        await DeviceClient(host, token).settings()
    except DeviceError as exc:
        if exc.status == 401:
            raise TOKEN_INVALID from None
        raise device_error(exc) from None


async def _give_token(host: str) -> str:
    """Set a new random token on a board that has none (user decision 2026-11-27)."""
    token = secrets.token_urlsafe(24)  # 32 characters, within the boards' 8 to 64
    try:
        await DeviceClient(host).post("settings", {"token": token})
    except DeviceError as exc:
        raise device_error(exc) from None
    await check_token(host, token)
    return token


async def _read_info(host: str) -> dict[str, Any]:
    try:
        return check_info(await DeviceClient(host).info())
    except DeviceError as exc:
        if exc.status is None:
            raise UNREACHABLE from None
        raise NOT_A_DEVICE from None


async def _token_for(host: str, info: dict[str, Any], token: str | None) -> str:
    """The token to store: the admin's (checked), or a new one for a board that has none."""
    if token is not None:
        await check_token(host, token)
        return token
    if info.get("auth") is False:
        token = await _give_token(host)
        log.info("Set a new token on device %s", info["id"])
        return token
    raise TOKEN_REQUIRED


async def add_device(db: AsyncSession, host: str, token: str | None) -> Device:
    info = await _read_info(host)
    # One registration per board at a time (one app instance): a second admin adding the same new
    # board waits, then finds it registered, instead of giving it a second token.
    async with host_lock(f"register:{info['id']}"):
        return await _register(db, host, info, token)


async def _register(db: AsyncSession, host: str, info: dict[str, Any], token: str | None) -> Device:
    if await db.scalar(select(Device.id).where(Device.device_id == info["id"])):
        raise DEVICE_EXISTS
    token = await _token_for(host, info, token)
    device = Device(
        device_id=info["id"],
        type=device_type(info["id"]),
        host=host,
        token_encrypted=encrypt_token(token),
        online=True,
        last_seen_at=datetime.now(UTC),
    )
    apply_info(device, info)
    db.add(device)
    try:
        await db.commit()
    except IntegrityError:  # registered meanwhile by another request
        await db.rollback()
        raise DEVICE_EXISTS from None
    log.info("Registered device %s", device.device_id)
    return device


async def delete_device(db: AsyncSession, pk: int) -> None:
    device = await get_device(db, pk)
    await db.delete(device)
    await db.commit()
    log.info("Removed device %s", device.device_id)
