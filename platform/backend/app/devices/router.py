"""/api/devices: the registry (list and read for users; add and remove for admins)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import RequireAdmin, RequireUser
from app.core import ratelimit
from app.core.db import get_session
from app.core.types import NO_NUL, IdPath
from app.devices import scan, service
from app.devices.schemas import (
    DeviceCreate,
    DeviceOut,
    DevicePage,
    ScanOut,
    ScanRanges,
    ScanRequest,
)

router = APIRouter(prefix="/devices", tags=["devices"])

Db = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_devices(
    user: RequireUser,
    db: Db,
    q: Annotated[str | None, Query(max_length=100, pattern=NO_NUL)] = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DevicePage:
    devices, total = await service.list_devices(db, q=q, page=page, size=size)
    return DevicePage(
        items=[DeviceOut.model_validate(d) for d in devices], total=total, page=page, size=size
    )


@router.post("", status_code=201)
async def add_device(body: DeviceCreate, admin: RequireAdmin, db: Db) -> DeviceOut:
    # It checks a secret against a board: limited like the other secret checks.
    ratelimit.DEVICE_ADD_USER.hit(str(admin.id))
    return DeviceOut.model_validate(await service.add_device(db, body.host, body.token))


# Before /{device_pk}: these paths would otherwise match it and fail as a non-integer id.
@router.get("/scan-ranges")
async def scan_ranges(admin: RequireAdmin) -> ScanRanges:
    return ScanRanges(ranges=scan.configured_ranges())


@router.post("/scan")
async def scan_network(admin: RequireAdmin, db: Db, body: ScanRequest | None = None) -> ScanOut:
    ratelimit.SCAN_USER.hit(str(admin.id))
    ranges = body.ranges if body and body.ranges else scan.configured_ranges()
    items, scanned, duration = await scan.scan(db, ranges)
    return ScanOut(items=items, scanned=scanned, duration_s=duration)


@router.get("/{device_pk}")
async def get_device(device_pk: IdPath, user: RequireUser, db: Db) -> DeviceOut:
    return DeviceOut.model_validate(await service.get_device(db, device_pk))


@router.delete("/{device_pk}", status_code=204)
async def delete_device(device_pk: IdPath, admin: RequireAdmin, db: Db) -> None:
    await service.delete_device(db, device_pk)
