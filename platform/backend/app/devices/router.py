"""/api/devices: the registry (list and read for users; add and remove for admins)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import AwareDatetime, StringConstraints
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import RequireAdmin, RequireUser
from app.core import ratelimit
from app.core.db import get_session
from app.core.types import MAX_DB_INT, NO_NUL, IdPath
from app.devices import commands, events, poller, scan, service
from app.devices.schemas import (
    CommandIn,
    CommandOut,
    DeviceCreate,
    DeviceOut,
    DevicePage,
    EventPage,
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
    device = await service.add_device(db, body.host, body.token)
    poller.notify()  # start polling it now
    return DeviceOut.model_validate(device)


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
    poller.notify()


EventNames = Annotated[
    list[Annotated[str, StringConstraints(max_length=32, pattern=r"^[a-z_]+$")]] | None,
    Query(alias="event", max_length=32),
]
Since = Annotated[AwareDatetime | None, Query(alias="from")]
Until = Annotated[AwareDatetime | None, Query(alias="to")]
Page = Annotated[int, Query(ge=1, le=100_000)]
Size = Annotated[int, Query(ge=1, le=100)]


@router.get("/{device_pk}/events")
async def device_events(
    device_pk: IdPath,
    user: RequireUser,
    db: Db,
    event: EventNames = None,
    since: Since = None,
    until: Until = None,
    page: Page = 1,
    size: Size = 50,
) -> EventPage:
    await service.get_device(db, device_pk)  # 404 for an unknown device
    items, total = await events.list_events(
        db, device_pk=device_pk, events=event, since=since, until=until, page=page, size=size
    )
    return EventPage(items=items, total=total, page=page, size=size)


events_router = APIRouter(prefix="/events", tags=["devices"])


@events_router.get("")
async def all_events(
    user: RequireUser,
    db: Db,
    device: Annotated[int | None, Query(ge=1, le=MAX_DB_INT)] = None,
    event: EventNames = None,
    since: Since = None,
    until: Until = None,
    page: Page = 1,
    size: Size = 50,
) -> EventPage:
    items, total = await events.list_events(
        db, device_pk=device, events=event, since=since, until=until, page=page, size=size
    )
    return EventPage(items=items, total=total, page=page, size=size)


Name = Annotated[str, Path(pattern=r"^[a-z0-9_]{1,32}$")]


@router.post("/{device_pk}/entities/{entity}/{command}")
async def send_command(
    device_pk: IdPath,
    entity: Name,
    command: Name,
    user: RequireUser,
    db: Db,
    body: CommandIn | None = None,
) -> CommandOut:
    ratelimit.COMMAND_USER.hit(str(user.id))
    params = body.model_dump(exclude_none=True) if body else {}
    return CommandOut(**await commands.send(db, device_pk, entity, command, params, user))
