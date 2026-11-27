import asyncio

import httpx
import pytest
from sqlalchemy import select

from app.core import ratelimit
from app.core.config import get_settings
from app.core.security import create_access_token
from app.devices import scan
from app.devices.models import Device
from app.users.models import Role
from tests.fakeboard import FakeBoard
from tests.helpers import auth


@pytest.fixture
async def as_admin(make_user):
    admin = await make_user("admin@example.com", role=Role.admin)
    return auth(create_access_token(admin.id, "admin"))


async def run(client, headers, ranges=None):
    body = {} if ranges is None else {"ranges": ranges}
    return await client.post("/api/devices/scan", json=body, headers=headers)


@pytest.fixture
def two_boards(lan):
    a = lan.add("10.1.3.103", FakeBoard(device_id="garage-3562d4", name="Garage"))
    b = lan.add("10.1.3.114", FakeBoard(device_id="garage-33ad84", name="Bench", token=None))
    return a, b


# ---- access ----


@pytest.mark.parametrize(
    ("method", "path"), [("post", "/api/devices/scan"), ("get", "/api/devices/scan-ranges")]
)
async def test_scanning_is_for_admins(client, make_user, method, path):
    assert (await client.request(method, path, json={})).status_code == 401
    for role in (Role.none, Role.user):
        user = await make_user(f"{role}@example.com", role=role)
        headers = auth(create_access_token(user.id, role.value))
        assert (await client.request(method, path, json={}, headers=headers)).status_code == 403


# ---- results ----


async def test_finds_the_boards_and_skips_everything_else(client, lan, two_boards, as_admin):
    lan.add("10.1.3.1").raw["info"] = httpx.Response(200, text="<html>router</html>")
    lan.add("10.1.3.2").raw["info"] = httpx.Response(404, text="nope")

    response = await run(client, as_admin, ["10.1.3.0/24"])

    assert response.status_code == 200
    body = response.json()
    assert body["scanned"] == 254
    assert body["duration_s"] >= 0
    assert body["items"] == [
        {
            "device_id": "garage-3562d4",
            "name": "Garage",
            "model": "Garage IoT Controller (UNO R4 WiFi)",
            "sw_version": "2.0.6",
            "host": "10.1.3.103",
            "auth": True,
            "registered": False,
            "id": None,
        },
        {
            "device_id": "garage-33ad84",
            "name": "Bench",
            "model": "Garage IoT Controller (UNO R4 WiFi)",
            "sw_version": "2.0.6",
            "host": "10.1.3.114",
            "auth": False,
            "registered": False,
            "id": None,
        },
    ]


async def test_registered_devices_come_last_with_their_id(client, db, two_boards, as_admin):
    db.add(Device(device_id="garage-3562d4", type="garage", name="Garage", host="10.1.3.103"))
    await db.commit()

    items = (await run(client, as_admin, ["10.1.3.0/24"])).json()["items"]

    assert [(i["device_id"], i["registered"]) for i in items] == [
        ("garage-33ad84", False),
        ("garage-3562d4", True),
    ]
    assert items[1]["id"] == 1


async def test_a_board_registered_by_ip_that_moved_gets_its_new_host(
    client, db, two_boards, as_admin
):
    db.add(Device(device_id="garage-3562d4", type="garage", name="Garage", host="10.1.3.20"))
    db.add(Device(device_id="garage-33ad84", type="garage", name="Bench", host="bench.lan"))
    await db.commit()

    await run(client, as_admin, ["10.1.3.0/24"])

    db.expire_all()
    hosts = {d.device_id: d.host for d in await db.scalars(select(Device))}
    assert hosts == {"garage-3562d4": "10.1.3.103", "garage-33ad84": "bench.lan"}


async def test_the_configured_ranges_are_the_default(client, lan, as_admin, monkeypatch):
    lan.add("192.168.5.6", FakeBoard(device_id="garage-000001"))
    monkeypatch.setenv("SCAN_RANGES", "192.168.5.0/29, 192.168.6.1")
    get_settings.cache_clear()
    try:
        ranges = (await client.get("/api/devices/scan-ranges", headers=as_admin)).json()
        body = (await run(client, as_admin)).json()
    finally:
        get_settings.cache_clear()

    assert ranges == {"ranges": ["192.168.5.0/29", "192.168.6.1"]}
    assert body["scanned"] == 7  # six hosts of the /29 plus the single address
    assert [i["device_id"] for i in body["items"]] == ["garage-000001"]


async def test_broken_configured_ranges_are_reported(client, as_admin, monkeypatch):
    monkeypatch.setenv("SCAN_RANGES", "10.1.3.0/24,not-a-range")
    get_settings.cache_clear()
    try:
        response = await run(client, as_admin)
    finally:
        get_settings.cache_clear()

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_scan_ranges"


def test_overlapping_ranges_are_probed_once_and_tiny_ranges_kept():
    assert scan.addresses(["10.0.0.0/30", "10.0.0.1/32", "10.0.0.8/31"]) == [
        "10.0.0.1",
        "10.0.0.2",
        "10.0.0.8",
        "10.0.0.9",
    ]


# ---- limits ----


async def test_more_than_1024_addresses_is_refused(client, as_admin):
    response = await run(client, as_admin, ["10.0.0.0/22", "10.0.4.1"])

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "scan_too_large"


async def test_a_full_22_is_allowed(client, as_admin):
    assert (await run(client, as_admin, ["10.0.0.0/22"])).json()["scanned"] == 1022


@pytest.mark.parametrize(
    "ranges",
    [[], ["10.1.3.0/33"], ["fe80::/64"], ["hello"], ["10.1.3.0/24"] * 17, ["1" * 44]],
)
async def test_invalid_ranges_are_refused(client, as_admin, ranges):
    response = await run(client, as_admin, ranges)

    assert response.status_code == 422


async def test_probes_run_in_parallel_but_bounded(client, lan, as_admin, monkeypatch):
    for i in range(1, 41):
        lan.add(f"10.1.4.{i}", FakeBoard(device_id=f"garage-{i:06x}")).delay_s = 0.01
    monkeypatch.setenv("SCAN_CONCURRENCY", "8")
    get_settings.cache_clear()
    try:
        body = (await run(client, as_admin, ["10.1.4.0/26"])).json()
    finally:
        get_settings.cache_clear()

    assert len(body["items"]) == 40
    assert 2 <= lan.max_in_flight <= 8


async def test_probes_use_the_scan_timeout(lan, monkeypatch):
    seen = []
    real = httpx.AsyncClient

    def spy(**kwargs):
        seen.append(kwargs["timeout"])
        return real(**kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", spy)
    monkeypatch.setenv("SCAN_TIMEOUT_S", "0.7")
    get_settings.cache_clear()
    try:
        await scan.probe_all(["10.1.3.9"])
    finally:
        get_settings.cache_clear()

    assert seen == [0.7]


async def test_one_scan_at_a_time(client, lan, as_admin, monkeypatch):
    lan.add("10.1.5.1").delay_s = 0.2
    probing = asyncio.Event()
    real_probe_all = scan.probe_all

    async def probe_all(hosts):
        probing.set()
        return await real_probe_all(hosts)

    monkeypatch.setattr(scan, "probe_all", probe_all)

    first = asyncio.create_task(run(client, as_admin, ["10.1.5.1"]))
    await asyncio.wait_for(probing.wait(), 5)  # the first scan is probing
    second = await run(client, as_admin, ["10.1.5.1"])
    assert (await first).status_code == 200

    assert second.status_code == 409
    assert second.json()["error"]["code"] == "scan_in_progress"
    assert (await run(client, as_admin, ["10.1.5.1"])).status_code == 200  # free again


async def test_scanning_is_rate_limited(client, as_admin, monkeypatch):
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "true")
    get_settings.cache_clear()
    try:
        for _ in range(ratelimit.SCAN_USER.limit):
            await run(client, as_admin, ["10.9.9.9"])
        response = await run(client, as_admin, ["10.9.9.9"])
    finally:
        get_settings.cache_clear()

    assert response.status_code == 429


async def test_null_ranges_mean_the_configured_ones(client, as_admin, monkeypatch):
    monkeypatch.setenv("SCAN_RANGES", "10.9.9.0/30")
    get_settings.cache_clear()
    try:
        response = await client.post("/api/devices/scan", json={"ranges": None}, headers=as_admin)
        no_body = await client.post("/api/devices/scan", headers=as_admin)
    finally:
        get_settings.cache_clear()

    assert response.json()["scanned"] == no_body.json()["scanned"] == 2


# ---- a board's id at another address never takes its token there ----


async def registered_at(db, host):
    db.add(Device(device_id="garage-3562d4", type="garage", name="Garage", host=host))
    await db.commit()


async def stored_host(db):
    db.expire_all()
    return (await db.scalars(select(Device))).one().host


async def test_a_copy_of_its_info_elsewhere_while_it_answers_at_home(client, db, lan, as_admin):
    lan.add("10.1.3.103", FakeBoard(device_id="garage-3562d4"))
    lan.add("10.1.3.66", FakeBoard(device_id="garage-3562d4"))  # an impostor
    await registered_at(db, "10.1.3.103")

    items = (await run(client, as_admin, ["10.1.3.0/24"])).json()["items"]

    assert await stored_host(db) == "10.1.3.103"
    assert [i["host"] for i in items] == ["10.1.3.66", "10.1.3.103"]  # both shown to the admin


async def test_its_id_at_two_new_addresses(client, db, lan, as_admin):
    lan.add("10.1.3.66", FakeBoard(device_id="garage-3562d4"))
    lan.add("10.1.3.67", FakeBoard(device_id="garage-3562d4"))
    await registered_at(db, "10.1.3.103")  # silent now

    await run(client, as_admin, ["10.1.3.0/24"])

    assert await stored_host(db) == "10.1.3.103"


async def test_still_answering_at_home_outside_the_scanned_range(client, db, lan, as_admin):
    lan.add("10.1.9.5", FakeBoard(device_id="garage-3562d4"))  # the real board, not scanned
    lan.add("10.1.3.66", FakeBoard(device_id="garage-3562d4"))
    await registered_at(db, "10.1.9.5")

    await run(client, as_admin, ["10.1.3.0/24"])

    assert await stored_host(db) == "10.1.9.5"


async def test_another_board_now_at_its_old_address_does_not_stop_the_move(
    client, db, lan, as_admin
):
    lan.add("10.1.9.5", FakeBoard(device_id="garage-000777"))  # the old IP went to another board
    lan.add("10.1.3.66", FakeBoard(device_id="garage-3562d4"))
    await registered_at(db, "10.1.9.5")

    await run(client, as_admin, ["10.1.3.0/24"])

    assert await stored_host(db) == "10.1.3.66"


async def test_a_cloned_id_is_logged_even_when_the_board_answers_at_home(
    client, db, lan, as_admin, caplog
):
    lan.add("10.1.3.103", FakeBoard(device_id="garage-3562d4"))
    lan.add("10.1.3.66", FakeBoard(device_id="garage-3562d4"))
    await registered_at(db, "10.1.3.103")

    await run(client, as_admin, ["10.1.3.0/24"])

    assert "Device garage-3562d4 answers at more than one address" in caplog.text
