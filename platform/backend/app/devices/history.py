"""Event history: the boards' logs, collected once, with absolute times.

A board keeps its last 64 events in RAM with `t` in seconds since its boot, newest first, and loses
them on a restart. The collector reads `GET /log` when the poller publishes a change (and at least
every LOG_READ_EVERY_S per online device), keeps one `DeviceBoot` per run of the board, and stores
the entries it has not stored yet: the fetched log overlaps the tail of what is stored.
"""

import asyncio
import contextlib
import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.core.types import MAX_DB_INT
from app.devices.bus import Rebooted, StateChanged, bus
from app.devices.client import DeviceError
from app.devices.commands import attribute
from app.devices.models import Device, DeviceBoot, DeviceEvent
from app.devices.service import client_for

log = logging.getLogger(__name__)

LOG_SIZE = 64  # entries a garage board keeps
BOOT_SLACK_S = 10  # read time - uptime moves by a request's latency, not by this much
DRIFT = 0.001  # …plus the board's clock drift over the time since the last read (generous)

Entry = tuple[int, str, str, str, int]  # t, event, source, reason, value
UINT32_MAX = 2**32 - 1
NAME = re.compile(r"^[a-z0-9_]{1,32}\Z")


@dataclass
class Log:
    uptime_s: int
    entries: list[Entry]  # oldest first


def _count(value: object, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= maximum


def parse_log(answer: dict[str, Any]) -> Log:
    """The `/log` answer, oldest first; malformed entries are skipped."""
    uptime = answer.get("uptime_s")
    events = answer.get("events")
    if not _count(uptime, MAX_DB_INT) or not isinstance(events, list):
        raise DeviceError(200, "device_bad_answer", "Not a /log answer")
    entries = []
    for e in reversed(events):
        if not isinstance(e, dict):
            continue
        entry = (e.get("t"), e.get("event"), e.get("source"), e.get("reason"), e.get("value"))
        types = (int, str, str, str, int)
        if all(
            isinstance(v, k) and not isinstance(v, bool) for v, k in zip(entry, types, strict=True)
        ):
            t, event, source, reason, value = entry
            # The board sends uint32 values; a t after the uptime would sit after the read itself.
            if not (_count(t, uptime) and _count(value, UINT32_MAX)):
                continue
            # Names are firmware identifiers (`door_opening`, `api`): anything else, a NUL or a lone
            # surrogate included, would not even go into the database.
            if not all(NAME.match(n) for n in (event, source, reason)):
                continue
            entries.append((t, event[:32], source[:16], reason[:32], value))
    return Log(uptime, entries)


def new_entries(stored: list[Entry], fetched: list[Entry]) -> list[Entry]:
    """The part of `fetched` (oldest first) not yet in `stored` (the current boot's tail, oldest
    first).

    A log that is not full holds everything since the boot: what is stored is its prefix, exactly.
    A full log has lost its oldest entries: skip the longest prefix of `fetched` that equals a
    suffix of `stored`. Only a full log of entries repeating in the same second (a burst of
    identical toggles) is ambiguous there; it is then counted short, never twice.
    """
    if len(fetched) < LOG_SIZE and len(stored) < LOG_SIZE and fetched[: len(stored)] == stored:
        return fetched[len(stored) :]
    for k in range(min(len(stored), len(fetched)), 0, -1):
        if stored[-k:] == fetched[:k]:
            return fetched[k:]
    return fetched


def same_boot(boot: DeviceBoot, started_at: datetime, uptime_s: int, now: datetime) -> bool:
    if uptime_s < boot.last_uptime_s:
        return False
    allowed = BOOT_SLACK_S + DRIFT * (now - boot.last_read_at).total_seconds()
    return abs((started_at - boot.started_at).total_seconds()) <= allowed


async def store_log(db: AsyncSession, device: Device, board_log: Log, now: datetime) -> int:
    """Store the new entries of `board_log` read at `now`; returns how many."""
    started_at = now - timedelta(seconds=board_log.uptime_s)
    boot = await db.scalar(
        select(DeviceBoot).where(DeviceBoot.device_pk == device.id).order_by(DeviceBoot.id.desc())
    )
    stored: list[Entry] = []
    if boot is not None and same_boot(boot, started_at, board_log.uptime_s, now):
        rows = await db.scalars(
            select(DeviceEvent)
            .where(DeviceEvent.boot_id == boot.id)
            .order_by(DeviceEvent.id.desc())
            .limit(LOG_SIZE)
        )
        stored = [(e.t, e.event, e.source, e.reason, e.value) for e in reversed(rows.all())]
    else:
        boot = DeviceBoot(device_pk=device.id, started_at=started_at)
        db.add(boot)
    boot.started_at, boot.last_uptime_s, boot.last_read_at = started_at, board_log.uptime_s, now
    await db.flush()
    # Entries older than the retention are left out before comparing: the clean-up deletes them
    # from what is stored, so the fetched log must not offer them again (a board up for longer than
    # the retention would otherwise get them re-inserted after every clean-up).
    oldest = now - timedelta(days=get_settings().event_retention_days)
    current = [x for x in board_log.entries if started_at + timedelta(seconds=x[0]) >= oldest]
    fresh = new_entries(stored, current)
    if stored and fresh and fresh is current:  # no overlap: some events were lost
        log.warning(
            "Device %s logged more than %d events between two reads", device.device_id, LOG_SIZE
        )
    rows = [
        DeviceEvent(
            device_pk=device.id,
            boot_id=boot.id,
            t=t,
            at=started_at + timedelta(seconds=t),
            event=event,
            source=source,
            reason=reason,
            value=value,
        )
        for t, event, source, reason, value in fresh
    ]
    await attribute(db, device.id, rows)  # before adding them: its queries must not see them
    db.add_all(rows)
    await db.commit()
    return len(fresh)


async def collect(device_pk: int) -> int | None:
    """Read one device's log and store what is new; None when it could not be read."""
    async with get_sessionmaker()() as db:
        snapshot = await db.get(Device, device_pk)
    if snapshot is None:
        return None
    try:
        board_log = parse_log(await client_for(snapshot).log())
    except (DeviceError, AppError) as exc:
        log.debug("Log of device %s not read: %s", snapshot.device_id, getattr(exc, "code", exc))
        return None
    now = datetime.now(UTC)
    async with get_sessionmaker()() as db:
        device = await db.get(Device, device_pk)
        if device is None:
            return None
        return await store_log(db, device, board_log, now)


class Collector:
    """Reads logs on the poller's events, and every LOG_READ_EVERY_S per online device."""

    def __init__(self) -> None:
        self.queue = bus.subscribe()
        self.last_read: dict[int, float] = {}

    async def due(self) -> list[int]:
        loop_now = asyncio.get_running_loop().time()
        every = get_settings().log_read_every_s
        async with get_sessionmaker()() as db:
            online = list(await db.scalars(select(Device.id).where(Device.online.is_(True))))
        return [pk for pk in online if loop_now - self.last_read.get(pk, -every) >= every]

    async def read(self, device_pk: int) -> None:
        """One device; its failure never stops the reads of the others."""
        self.last_read[device_pk] = asyncio.get_running_loop().time()
        try:
            await collect(device_pk)
        except Exception:
            log.exception("Reading the log of device %s failed", device_pk)

    async def step(self, wait_s: float) -> None:
        with contextlib.suppress(TimeoutError):
            event = await asyncio.wait_for(self.queue.get(), wait_s)
            if isinstance(event, StateChanged | Rebooted):
                await self.read(event.device_pk)
        for pk in await self.due():
            await self.read(pk)

    async def run(self) -> None:
        while True:
            try:
                await self.step(1.0)
            except Exception:
                log.exception("Event history collection failed")
                await asyncio.sleep(1.0)

    def close(self) -> None:
        bus.unsubscribe(self.queue)


_collector: Collector | None = None


def start() -> asyncio.Task:
    """Subscribe before the poller starts, so its first events are not missed."""
    global _collector
    _collector = Collector()
    return asyncio.create_task(_collector.run(), name="history-collector")


async def stop(task: asyncio.Task) -> None:
    global _collector
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    collector, _collector = _collector, None  # set by start(), which the lifespan ran first
    collector.close()
