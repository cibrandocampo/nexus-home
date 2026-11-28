"""Discovery: probe `GET /api/v1/info` on every address of some IPv4 ranges.

Boards are slow WiFi modules: few probes at a time (SCAN_CONCURRENCY), a short timeout
(SCAN_TIMEOUT_S), and one scan at a time in the app.
"""

import asyncio
import ipaddress
import logging
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import AppError
from app.devices.client import DeviceClient, DeviceError
from app.devices.models import Device
from app.devices.service import check_info

log = logging.getLogger(__name__)

MAX_ADDRESSES = 1024  # a /22: a typo such as /8 must not probe sixteen million addresses
SCAN_IN_PROGRESS = AppError(409, "scan_in_progress", "A scan is already running")
SCAN_TOO_LARGE = AppError(
    400, "scan_too_large", f"The ranges hold more than {MAX_ADDRESSES} addresses"
)
INVALID_RANGES = AppError(400, "invalid_scan_ranges", "SCAN_RANGES is not a list of IPv4 CIDRs")

_scanning = False  # one scan at a time (one app instance, one event loop)


@dataclass
class Found:
    host: str
    info: dict[str, Any]


def parse_range(value: str) -> ipaddress.IPv4Network:
    """An IPv4 CIDR (`10.1.3.0/24`, host bits allowed) or a single address; ValueError otherwise."""
    network = ipaddress.ip_network(value.strip(), strict=False)
    if not isinstance(network, ipaddress.IPv4Network):
        raise ValueError("IPv4 only")
    return network


def configured_ranges() -> list[str]:
    return [r.strip() for r in get_settings().scan_ranges.split(",") if r.strip()]


def addresses(ranges: list[str]) -> list[str]:
    try:
        networks = [parse_range(r) for r in ranges]
    except ValueError:
        raise INVALID_RANGES from None
    if sum(n.num_addresses for n in networks) > MAX_ADDRESSES:
        raise SCAN_TOO_LARGE
    seen: dict[str, None] = {}
    for network in networks:
        hosts = list(network.hosts()) if network.prefixlen < 31 else list(network)
        seen.update((str(ip), None) for ip in hosts)
    return list(seen)


async def _probe(host: str, gate: asyncio.Semaphore, wait_s: float) -> Found | None:
    async with gate:
        try:
            info = check_info(await DeviceClient(host, timeout=wait_s).info())
        except DeviceError, AppError:  # silent, or something else answers HTTP there
            return None
    return Found(host, info)


async def probe_all(hosts: list[str]) -> list[Found]:
    settings = get_settings()
    gate = asyncio.Semaphore(settings.scan_concurrency)
    results = await asyncio.gather(*(_probe(h, gate, settings.scan_timeout_s) for h in hosts))
    return [r for r in results if r is not None]


def _is_ip(host: str) -> bool:
    try:
        ipaddress.IPv4Address(host)
    except ValueError:
        return False
    return True


async def _still_there(device: Device) -> bool:
    """Whether the board still answers at its stored host as itself."""
    try:
        info = await DeviceClient(device.host, timeout=get_settings().scan_timeout_s).info()
    except DeviceError:
        return False
    return info.get("id") == device.device_id


async def _follow_moves(db: AsyncSession, found: list[Found]) -> dict[str, Device]:
    """Registered devices among `found`, by device id. A board registered by IP that answered at
    one other IP (DHCP) gets its new host. Never moved (the stored token would go to whoever
    copies a board's /info): when its id answers at several addresses, or when it still answers
    at its stored host. A hostname is kept: it already follows the board."""
    hosts: dict[str, list[str]] = {}
    for f in found:
        hosts.setdefault(f.info["id"], []).append(f.host)
    devices = {
        d.device_id: d
        for d in await db.scalars(select(Device).where(Device.device_id.in_(list(hosts))))
    }
    for device_id, device in devices.items():
        seen = hosts[device_id]
        if len(seen) > 1 or (device.host not in seen and await _still_there(device)):
            log.warning("Device %s answers at more than one address: host kept", device_id)
            continue
        if device.host in seen or not _is_ip(device.host):
            continue
        log.info("Device %s moved to a new address", device_id)
        device.host = seen[0]
    await db.commit()
    return devices


async def scan(db: AsyncSession, ranges: list[str]) -> tuple[list[dict[str, Any]], int, float]:
    global _scanning
    hosts = addresses(ranges)
    if _scanning:
        raise SCAN_IN_PROGRESS
    _scanning = True
    started = time.monotonic()
    try:
        found = await probe_all(hosts)
    finally:
        _scanning = False
    registered = await _follow_moves(db, found)
    items = [_item(f, registered.get(f.info["id"])) for f in found]
    items.sort(key=lambda i: (i["registered"], ipaddress.IPv4Address(i["host"])))
    return items, len(hosts), round(time.monotonic() - started, 2)


def _item(f: Found, device: Device | None) -> dict[str, Any]:
    def text(key: str) -> str:
        value = f.info.get(key)
        return value[:128] if isinstance(value, str) else ""

    return {
        "device_id": f.info["id"],
        "name": text("name"),
        "model": text("model"),
        "sw_version": text("sw_version"),
        "host": f.host,
        "auth": f.info.get("auth") is not False,
        "registered": device is not None,
        "id": device.id if device else None,
    }
