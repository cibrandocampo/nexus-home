"""State polling: one task per registered device, under a supervisor started in the lifespan.

The one exception to "background work only in core/scheduler.py" (platform-backend): device I/O
runs continuously, one small task per board. Each task reads `GET /state` every POLL_INTERVAL_S,
saves it when `rev` changes, tracks online/offline and reboots, and publishes on the bus.
"""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.errors import AppError
from app.core.types import MAX_DB_INT
from app.devices.bus import Rebooted, StateChanged, WentOffline, WentOnline, bus
from app.devices.client import DeviceError
from app.devices.models import Device
from app.devices.service import apply_info, check_info, client_for

log = logging.getLogger(__name__)

RESYNC_S = 30  # the supervisor re-reads the registry this often (and when notified)
RESTART_PAUSE_S = 5  # after an unexpected error in a device task
RETRY_S = 0.5  # after a failed poll, while the device still counts as online
REBOOT_SLACK_S = 5  # uptime and wall clock drift apart by a request or two, not by this much


def apply_state(
    device: Device, state: dict[str, Any], now: datetime, *, force: bool = False
) -> bool:
    """Store a fresh `/state` answer; True when it was saved (a new `rev`, or `force` after a
    restart: `rev` lives in the board's RAM and starts again at every boot, so an equal `rev`
    then says nothing)."""
    device.last_seen_at = now
    uptime = state.get("uptime_s")
    device.uptime_s = uptime if isinstance(uptime, int) and 0 <= uptime <= MAX_DB_INT else None
    if state["rev"] == device.rev and not force:
        return False
    device.state = state
    device.rev = state["rev"]
    return True


def restarted(device: Device, uptime_s: int, now: datetime) -> bool:
    """Whether the board restarted since it was last seen: its uptime went down, or it is below
    what it would be by now (the last uptime plus the time since, minus a slack). The second
    catches a restart while it was offline longer than its previous uptime."""
    if device.uptime_s is None or device.last_seen_at is None:
        return False
    if uptime_s < device.uptime_s:
        return True
    expected = device.uptime_s + (now - device.last_seen_at).total_seconds()
    return uptime_s < expected - REBOOT_SLACK_S


@dataclass
class Answer:
    state: dict[str, Any]
    rebooted: bool
    info: dict[str, Any] | None  # re-read after a restart, None otherwise


class DevicePoller:
    """Polls one device; `poll_once` returns the seconds until the next poll, None when the
    device is no longer registered. No database connection is held while the board answers."""

    def __init__(self, device_pk: int) -> None:
        self.device_pk = device_pk
        self.failures = 0

    async def poll_once(self) -> float | None:
        settings = get_settings()
        async with get_sessionmaker()() as db:
            snapshot = await db.get(Device, self.device_pk)  # detached on close, fields loaded
        if snapshot is None:
            return None
        try:
            answer: Answer | Exception = await _ask(snapshot)
        except (DeviceError, AppError) as exc:
            answer = exc
        async with get_sessionmaker()() as db:
            device = await db.get(Device, self.device_pk)
            if device is None:
                return None
            if isinstance(answer, Exception):
                events = self._failed(device, answer)
            else:
                self.failures = 0
                events = _answered(device, answer)
            online, failing = device.online, self.failures > 0
            await db.commit()
        for event in events:
            bus.publish(event)
        if not online:
            return settings.poll_offline_interval_s
        # A failed poll already waited its timeout: try again soon, so offline is noticed in about
        # POLL_OFFLINE_AFTER timeouts.
        return RETRY_S if failing else settings.poll_interval_s

    def _failed(self, device: Device, exc: Exception) -> list:
        self.failures += 1
        code = getattr(exc, "code", type(exc).__name__)
        log.debug("Poll of device %s failed: %s", device.device_id, code)
        if device.online and self.failures >= get_settings().poll_offline_after:
            device.online = False
            log.info("Device %s is offline", device.device_id)
            return [WentOffline(device.id)]
        return []

    async def run(self) -> None:
        while True:
            try:
                delay = await self.poll_once()
            except Exception:
                log.exception("Polling device %s failed unexpectedly", self.device_pk)
                delay = RESTART_PAUSE_S
            if delay is None:
                return
            await asyncio.sleep(delay)


def _answered(device: Device, answer: Answer) -> list:
    events: list = []
    if not device.online:
        device.online = True
        log.info("Device %s is back online", device.device_id)
        events.append(WentOnline(device.id))
    if answer.rebooted:
        log.info("Device %s restarted", device.device_id)
        events.append(Rebooted(device.id, answer.state["uptime_s"]))
        apply_info(device, answer.info)
    if apply_state(device, answer.state, datetime.now(UTC), force=answer.rebooted):
        events.append(StateChanged(device.id, answer.state["rev"]))
    return events


async def _ask(device: Device) -> Answer:
    """`/state`, and `/info` again after a restart; raises when the answer is not this board's."""
    client = client_for(device)
    state = await client.state()
    if not isinstance(state.get("rev"), int):
        raise DeviceError(200, "device_bad_answer", "No rev in /state")
    uptime = state.get("uptime_s")
    rebooted = isinstance(uptime, int) and restarted(device, uptime, datetime.now(UTC))
    info: dict[str, Any] | None = None
    if rebooted:
        try:
            info = check_info(await client.info())
        except DeviceError, AppError:
            # Whose state is this? Not saved until /info confirms it (the next poll retries).
            log.info("Could not re-read /info of device %s after its restart", device.device_id)
            raise DeviceError(None, "device_unreachable", "No /info after a restart") from None
        if info["id"] != device.device_id:
            # Another board answers at this address now (DHCP): never take its identity or state.
            log.warning("Another device answers at the address of %s", device.device_id)
            raise DeviceError(200, "device_mismatch", "Another device answers at this address")
    return Answer(state, rebooted, info)


class Supervisor:
    def __init__(self) -> None:
        self.tasks: dict[int, asyncio.Task] = {}
        self._wake = asyncio.Event()

    def notify(self) -> None:
        """The registry changed: start or stop device tasks now instead of at the next resync."""
        self._wake.set()

    async def sync(self) -> None:
        async with get_sessionmaker()() as db:
            registered = set(await db.scalars(select(Device.id)))
        for pk in [pk for pk in self.tasks if pk not in registered or self.tasks[pk].done()]:
            self.tasks.pop(pk).cancel()
        for pk in registered - set(self.tasks):
            self.tasks[pk] = asyncio.create_task(DevicePoller(pk).run(), name=f"poll-{pk}")

    async def run(self) -> None:
        while True:
            try:
                await self.sync()
            except Exception:
                log.exception("Device supervisor could not read the registry")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self._wake.wait(), RESYNC_S)
            self._wake.clear()

    async def stop(self) -> None:
        tasks = list(self.tasks.values())
        self.tasks.clear()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task


_supervisor: Supervisor | None = None


def notify() -> None:
    """Called after a device is added or removed; a no-op when polling is not running."""
    if _supervisor is not None:
        _supervisor.notify()


def start() -> asyncio.Task:
    global _supervisor
    _supervisor = Supervisor()
    return asyncio.create_task(_supervisor.run(), name="device-supervisor")


async def stop(task: asyncio.Task) -> None:
    global _supervisor
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task
    supervisor, _supervisor = _supervisor, None  # set by start(), which the lifespan ran first
    await supervisor.stop()
