import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.core.scheduler import cleanup
from app.core.security import create_access_token
from app.devices import history
from app.devices.bus import StateChanged, WentOnline, bus
from app.devices.client import DeviceError
from app.devices.crypto import encrypt_token
from app.devices.history import Collector, Log, collect, new_entries, parse_log, store_log
from app.devices.models import Device, DeviceBoot, DeviceEvent
from app.users.models import Role
from tests.fakeboard import garage_state
from tests.helpers import auth

HOST = "10.1.3.50"
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=UTC)


def entry(t, event="light_on", source="api", reason="none", value=0):
    return {"t": t, "event": event, "source": source, "reason": reason, "value": value}


def e(t, event="light_on", source="api", reason="none", value=0):
    return (t, event, source, reason, value)


@pytest.fixture
async def device(db, lan):
    lan.add(HOST)
    row = Device(
        device_id="garage-abc123",
        type="garage",
        name="Garage",
        host=HOST,
        token_encrypted=encrypt_token("board-token-1"),
        entities=[],
        online=True,
    )
    db.add(row)
    await db.commit()
    return row


async def stored(_db=None) -> list[DeviceEvent]:
    # A session of its own: expiring the test's session would leave its objects needing lazy loads.
    async with get_sessionmaker()() as fresh:
        return list(await fresh.scalars(select(DeviceEvent).order_by(DeviceEvent.id)))


async def boots(_db=None) -> list[DeviceBoot]:
    async with get_sessionmaker()() as fresh:
        return list(await fresh.scalars(select(DeviceBoot).order_by(DeviceBoot.id)))


# ---- parsing and overlap ----


def test_the_log_is_read_oldest_first_and_bad_entries_are_skipped():
    answer = {
        "uptime_s": 90,
        "events": [
            entry(80, "door_open"),
            {"t": 70, "event": "x"},  # missing fields
            entry(60, value=True),  # a boolean is not a number
            "nonsense",
            entry(50, "boot", source="none"),
        ],
    }

    assert parse_log(answer) == Log(90, [e(50, "boot", "none"), e(80, "door_open")])


@pytest.mark.parametrize(
    "answer", [{}, {"uptime_s": "9", "events": []}, {"uptime_s": 9, "events": {}}]
)
def test_an_answer_that_is_not_a_log(answer):
    with pytest.raises(DeviceError):
        parse_log(answer)


def test_a_long_source_is_cut_to_its_column():
    log = parse_log({"uptime_s": 1, "events": [entry(1, "e" * 32, "s" * 20, "r" * 32)]})

    assert log.entries == [e(1, "e" * 32, "s" * 16, "r" * 32)]


@pytest.mark.parametrize(
    ("stored", "fetched", "new"),
    [
        ([], [e(1), e(2)], [e(1), e(2)]),  # first read
        ([e(1), e(2)], [e(1), e(2)], []),  # nothing new
        ([e(1), e(2)], [e(1), e(2), e(3)], [e(3)]),
        ([e(1), e(2), e(3)], [e(2), e(3), e(4), e(5)], [e(4), e(5)]),  # the log slid
        ([e(1), e(2)], [e(7), e(8)], [e(7), e(8)]),  # no overlap: more than a log since
        # The same event twice in one second, then a third: one new.
        ([e(5, "light_off"), e(5), e(5)], [e(5, "light_off"), e(5), e(5), e(5)], [e(5)]),
    ],
)
def test_new_entries(stored, fetched, new):
    assert new_entries(stored, fetched) == new


def test_a_burst_of_identical_toggles_is_counted_exactly_until_the_log_is_full():
    total = [e(0, "light_on" if i % 2 == 0 else "light_off") for i in range(64)]
    stored: list = []
    for end in (10, 25, 40, 55, 63, 64):  # the log is full only at the last read
        stored += new_entries(stored[-64:], total[:end])

    assert stored == total


def test_a_full_log_of_identical_toggles_is_counted_short_never_twice():
    # The documented limit: the overlap cannot be told apart, the longest is taken.
    total = [e(0, "light_on" if i % 2 == 0 else "light_off") for i in range(70)]
    stored = total[:60]

    new = new_entries(stored, total[6:70])

    assert new == total[66:]  # 4 of the 10 new ones: short, and no duplicate


# ---- storing ----


async def test_the_first_read_stores_the_log_with_absolute_times(db, device):
    count = await store_log(db, device, Log(100, [e(0, "boot", "none"), e(40, "door_open")]), NOW)

    assert count == 2
    rows = await stored(db)
    assert [(r.event, r.at) for r in rows] == [
        ("boot", NOW - timedelta(seconds=100)),
        ("door_open", NOW - timedelta(seconds=60)),
    ]
    (boot,) = await boots(db)
    assert (boot.started_at, boot.last_uptime_s, boot.last_read_at) == (
        NOW - timedelta(seconds=100),
        100,
        NOW,
    )
    assert {r.boot_id for r in rows} == {boot.id}


async def test_a_later_read_stores_only_what_is_new(db, device):
    await store_log(db, device, Log(100, [e(0), e(40)]), NOW)

    later = NOW + timedelta(seconds=30)
    count = await store_log(db, device, Log(130, [e(0), e(40), e(120, "light_off")]), later)

    assert count == 1
    assert [r.event for r in await stored(db)] == ["light_on", "light_on", "light_off"]
    assert len(await boots(db)) == 1


async def test_a_restart_opens_a_new_boot(db, device):
    await store_log(db, device, Log(100, [e(0, "boot", "none"), e(40)]), NOW)

    later = NOW + timedelta(seconds=30)
    await store_log(db, device, Log(5, [e(0, "boot", "none")]), later)

    first, second = await boots(db)
    assert second.started_at == later - timedelta(seconds=5)
    rows = await stored(db)
    assert [(r.event, r.boot_id) for r in rows] == [
        ("boot", first.id),
        ("light_on", first.id),
        ("boot", second.id),
    ]


async def test_a_restart_while_nobody_read_the_log_is_still_a_new_boot(db, device):
    await store_log(db, device, Log(100, [e(0, "boot", "none")]), NOW)

    # Two hours later the board answers with an uptime of one hour: it restarted meanwhile.
    later = NOW + timedelta(hours=2)
    await store_log(db, device, Log(3600, [e(0, "boot", "none")]), later)

    assert len(await boots(db)) == 2
    assert len(await stored(db)) == 2


async def test_clock_drift_is_not_a_restart(db, device):
    await store_log(db, device, Log(100, [e(0)]), NOW)

    # A day later the board's clock is 20 s behind the server's: within the drift allowance.
    later = NOW + timedelta(days=1)
    await store_log(db, device, Log(100 + 86_400 - 20, [e(0), e(500)]), later)

    assert len(await boots(db)) == 1
    assert len(await stored(db)) == 2


async def test_a_full_log_with_no_overlap_is_stored_and_logged(db, device, caplog):
    await store_log(db, device, Log(100, [e(1)]), NOW)
    fresh = [e(200 + i) for i in range(64)]

    await store_log(db, device, Log(300, fresh), NOW + timedelta(seconds=200))

    assert len(await stored(db)) == 65
    assert "Device garage-abc123 logged more than 64 events between two reads" in caplog.text


# ---- collector ----


async def test_collect_reads_the_board_log(db, lan, device):
    board = lan.boards[HOST]
    board.state = garage_state(uptime_s=30)
    board.log = [entry(20, "door_opening"), entry(0, "boot", source="none")]

    assert await collect(device.id) == 2
    assert await collect(device.id) == 0
    assert [r.event for r in await stored(db)] == ["boot", "door_opening"]


async def test_collect_skips_a_board_that_does_not_answer(db, lan, device):
    lan.boards[HOST].unreachable = True

    assert await collect(device.id) is None
    assert await stored(db) == []


async def test_collect_skips_a_removed_device(db, device, monkeypatch):
    assert await collect(999) is None

    async def remove(pk):
        from app.core.db import get_sessionmaker

        async with get_sessionmaker()() as other:
            await other.delete(await other.get(Device, pk))
            await other.commit()

    original = history.client_for

    def client_then_remove(snapshot):
        client = original(snapshot)
        real_log = client.log

        async def log():
            answer = await real_log()
            await remove(snapshot.id)
            return answer

        client.log = log
        return client

    monkeypatch.setattr(history, "client_for", client_then_remove)

    assert await collect(device.id) is None


async def test_the_collector_reads_on_a_state_change(db, lan, device):
    collector = Collector()
    collector.last_read[device.id] = asyncio.get_running_loop().time()  # not due by time
    lan.boards[HOST].log = [entry(5, "light_on")]
    try:
        bus.publish(WentOnline(device.id))  # not a reason to read
        await collector.step(0.01)
        assert await stored(db) == []

        bus.publish(StateChanged(device.id, 2))
        await collector.step(0.5)
        assert [r.event for r in await stored(db)] == ["light_on"]
    finally:
        collector.close()


async def test_online_devices_are_read_at_least_every_interval(db, lan, device):
    other = Device(
        device_id="garage-000002", type="garage", name="Off", host="10.1.3.99", online=False
    )
    db.add(other)
    await db.commit()
    collector = Collector()
    try:
        assert await collector.due() == [device.id]  # never read; the offline one is not due
        await collector.step(0.01)
        assert await collector.due() == []
        collector.last_read[device.id] -= get_settings().log_read_every_s
        assert await collector.due() == [device.id]
    finally:
        collector.close()


async def test_the_collector_survives_an_error(monkeypatch, caplog):
    collector = Collector()
    calls = []

    async def step(wait_s):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        raise asyncio.CancelledError

    monkeypatch.setattr(collector, "step", step)
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    try:
        with pytest.raises(asyncio.CancelledError):
            await collector.run()
    finally:
        collector.close()

    assert len(calls) == 2
    assert "Event history collection failed" in caplog.text


_real_sleep = asyncio.sleep


async def _no_sleep(_):
    await _real_sleep(0)


async def test_start_and_stop_subscribe_and_unsubscribe():
    task = history.start()
    collector = history._collector
    assert collector.queue in bus._queues

    await history.stop(task)

    assert task.done()
    assert collector.queue not in bus._queues
    assert history._collector is None


# ---- retention ----


async def test_old_events_and_the_boots_they_leave_empty_are_deleted(db, device):
    old = NOW - timedelta(days=400)
    await store_log(db, device, Log(10, [e(1, "boot", "none")]), old)
    await store_log(db, device, Log(10, [e(1, "boot", "none")]), old + timedelta(days=10))
    await store_log(db, device, Log(10, [e(1, "boot", "none")]), datetime.now(UTC))
    first, second, latest = await boots(db)
    # A latest boot whose events all expired is kept: the next read continues it.
    lone = Device(device_id="garage-000009", type="garage", name="Lone", host="10.1.3.9")
    db.add(lone)
    await db.commit()
    await store_log(db, lone, Log(10, [e(1)]), old)

    await cleanup(db)

    remaining = await stored(db)
    assert [r.boot_id for r in remaining] == [latest.id]
    kept = {b.id for b in await boots(db)}
    assert first.id not in kept and second.id not in kept and latest.id in kept
    assert len(kept) == 2  # the lone device's latest boot stays


async def test_retention_follows_the_setting(db, device, monkeypatch):
    await store_log(db, device, Log(10, [e(1)]), datetime.now(UTC) - timedelta(days=3))
    monkeypatch.setenv("EVENT_RETENTION_DAYS", "2")
    get_settings.cache_clear()
    try:
        await cleanup(db)
    finally:
        get_settings.cache_clear()

    assert await stored(db) == []


# ---- API ----


@pytest.fixture
async def as_user(make_user):
    user = await make_user("ana@example.com", role=Role.user, first_name="Ana", last_name="Pérez")
    return auth(create_access_token(user.id, "user")), user


@pytest.fixture
async def history_rows(db, device):
    other = Device(device_id="garage-000002", type="garage", name="Shed", host="10.1.3.99")
    db.add(other)
    await db.commit()
    await store_log(db, device, Log(100, [e(0, "boot", "none"), e(50, "door_open"), e(90)]), NOW)
    await store_log(db, other, Log(100, [e(60, "door_closed")]), NOW)
    return device, other


async def test_the_history_needs_a_role(client, make_user, device):
    assert (await client.get("/api/events")).status_code == 401
    assert (await client.get(f"/api/devices/{device.id}/events")).status_code == 401
    none = await make_user("none@example.com", role=Role.none)
    headers = auth(create_access_token(none.id, "none"))
    assert (await client.get("/api/events", headers=headers)).status_code == 403
    assert (
        await client.get(f"/api/devices/{device.id}/events", headers=headers)
    ).status_code == 403


async def test_all_events_newest_first_with_their_device(client, as_user, history_rows):
    headers, _ = as_user

    page = (await client.get("/api/events", headers=headers)).json()

    assert (page["total"], page["page"], page["size"]) == (4, 1, 50)
    assert [(i["event"], i["device"]["name"]) for i in page["items"]] == [
        ("light_on", "Garage"),
        ("door_closed", "Shed"),
        ("door_open", "Garage"),
        ("boot", "Garage"),
    ]
    first = page["items"][0]
    assert first["at"] == "2026-11-27T11:59:50Z"
    assert (first["source"], first["reason"], first["value"], first["user"]) == (
        "api",
        "none",
        0,
        None,
    )


async def test_one_device_s_events(client, as_user, history_rows):
    headers, _ = as_user
    _, other = history_rows

    page = (await client.get(f"/api/devices/{other.id}/events", headers=headers)).json()

    assert [i["event"] for i in page["items"]] == ["door_closed"]


async def test_filters(client, as_user, history_rows):
    headers, _ = as_user
    device, _ = history_rows

    def events(query):
        return client.get(f"/api/events?{query}", headers=headers)

    by_device = (await events(f"device={device.id}")).json()
    assert by_device["total"] == 3
    by_type = (await events("event=door_open&event=door_closed")).json()
    assert {i["event"] for i in by_type["items"]} == {"door_open", "door_closed"}
    window = (await events("from=2026-11-27T11:58:30Z&to=2026-11-27T11:59:50Z")).json()
    assert [i["event"] for i in window["items"]] == ["door_closed", "door_open"]  # to is exclusive
    paged = (await events("size=2&page=2")).json()
    assert [i["event"] for i in paged["items"]] == ["door_open", "boot"]


async def test_the_user_who_caused_an_event_is_named(client, db, as_user, history_rows):
    headers, user = as_user
    row = (await stored())[1]
    await db.execute(update(DeviceEvent).where(DeviceEvent.id == row.id).values(user_id=user.id))
    await db.commit()

    items = (await client.get("/api/events", headers=headers)).json()["items"]

    assert [i["user"] for i in items if i["user"]] == [{"id": user.id, "name": "Ana Pérez"}]


async def test_a_user_without_a_name_is_shown_without_one(
    client, db, make_user, as_user, history_rows
):
    headers, _ = as_user
    nameless = await make_user("x@example.com", role=Role.user)
    row = (await stored())[0]
    await db.execute(
        update(DeviceEvent).where(DeviceEvent.id == row.id).values(user_id=nameless.id)
    )
    await db.commit()

    items = (await client.get("/api/events", headers=headers)).json()["items"]

    assert {"id": nameless.id, "name": None} in [i["user"] for i in items]
    assert "x@example.com" not in str(items)


@pytest.mark.parametrize(
    "query",
    [
        "from=2026-11-27T10:00:00",
        "to=yesterday",
        "event=Door",
        "event=" + "a" * 33,
        "size=101",
        "device=0",
    ],
)
async def test_invalid_filters(client, as_user, query):
    headers, _ = as_user

    assert (await client.get(f"/api/events?{query}", headers=headers)).status_code == 422


async def test_events_of_an_unknown_device(client, as_user):
    headers, _ = as_user

    response = await client.get("/api/devices/999/events", headers=headers)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "device_not_found"


async def test_events_go_with_their_device(client, db, as_user, history_rows):
    _, other = history_rows

    await db.delete(await db.get(Device, other.id))
    await db.commit()

    assert len(await stored(db)) == 3
    assert (await db.scalar(select(func.count()).select_from(DeviceBoot))) == 1


# ---- values out of range ----


@pytest.mark.parametrize(
    "bad",
    [
        entry(-5),  # before its own boot
        entry(500),  # after the read (uptime 100)
        entry(10, value=-1),
        entry(10, value=2**32),
        entry(2**31),
        entry(10**12),
    ],
)
def test_entries_out_of_range_are_skipped(bad):
    log = parse_log({"uptime_s": 100, "events": [entry(90, "light_off"), bad, entry(0, "boot")]})

    assert log.entries == [e(0, "boot"), e(90, "light_off")]


def test_the_largest_values_a_board_sends_fit():
    log = parse_log({"uptime_s": 2**31 - 1, "events": [entry(2**31 - 1, value=2**32 - 1)]})

    assert log.entries == [e(2**31 - 1, value=2**32 - 1)]


@pytest.mark.parametrize("uptime", [-1, 2**31, 2**63, True])
def test_an_uptime_out_of_range_is_not_a_log(uptime):
    with pytest.raises(DeviceError):
        parse_log({"uptime_s": uptime, "events": []})


async def test_one_bad_entry_does_not_stop_the_history(db, lan, device):
    board = lan.boards[HOST]
    board.state = garage_state(uptime_s=30)
    board.log = [entry(20, value=2**63), entry(10, "door_open"), entry(0, "boot", source="none")]

    assert await collect(device.id) == 2
    board.log = [entry(25, "light_on"), *board.log]
    assert await collect(device.id) == 1
    assert [r.event for r in await stored()] == ["boot", "door_open", "light_on"]


async def test_a_board_up_for_longer_than_the_retention_gets_nothing_back(db, device, monkeypatch):
    monkeypatch.setenv("EVENT_RETENTION_DAYS", "1")
    get_settings.cache_clear()
    try:
        now = datetime.now(UTC)
        three_days = 3 * 86_400
        board_log = Log(three_days, [e(0, "boot", "none"), e(three_days - 60, "light_on")])
        await store_log(db, device, board_log, now)
        await cleanup(db)
        later = Log(three_days + 30, board_log.entries)  # the same boot, 30 s later
        await store_log(db, device, later, now + timedelta(seconds=30))
        await cleanup(db)
    finally:
        get_settings.cache_clear()

    assert [r.event for r in await stored()] == ["light_on"]  # the boot entry is past the retention


# ---- texts the database cannot hold ----


@pytest.mark.parametrize(
    "bad",
    [
        entry(10, "door\x00open"),
        entry(10, source="\ud800"),
        entry(10, reason="Sensor"),
        entry(10, "door opening"),
        entry(10, ""),
        entry(10, "e" * 33),
    ],
)
def test_entries_whose_names_are_not_identifiers_are_skipped(bad):
    log = parse_log({"uptime_s": 100, "events": [bad, entry(0, "boot")]})

    assert log.entries == [e(0, "boot")]


@pytest.mark.parametrize("bad", ["\\u0000", "\\ud800"])
async def test_one_entry_with_an_unstorable_text_does_not_stop_the_history(db, lan, device, bad):
    import httpx

    board = lan.boards[HOST]
    body = (
        '{"uptime_s": 30, "events": [{"t": 20, "event": "door' + bad + '", "source": "api",'
        ' "reason": "none", "value": 0}, {"t": 0, "event": "boot", "source": "none",'
        ' "reason": "none", "value": 0}]}'
    )
    board.raw["log"] = httpx.Response(
        200, content=body.encode(), headers={"Content-Type": "application/json"}
    )

    assert await collect(device.id) == 1
    assert [r.event for r in await stored()] == ["boot"]


async def test_one_device_failing_does_not_stop_the_others(db, lan, device, monkeypatch, caplog):
    other = Device(
        device_id="garage-000002", type="garage", name="Shed", host="10.1.3.99", online=True
    )
    db.add(other)
    await db.commit()
    real_collect = history.collect
    read = []

    async def collect_or_fail(pk):
        read.append(pk)
        if pk == device.id:
            raise RuntimeError("boom")
        return await real_collect(pk)

    monkeypatch.setattr(history, "collect", collect_or_fail)
    collector = Collector()
    try:
        await collector.step(0.01)
    finally:
        collector.close()

    assert sorted(read) == sorted([device.id, other.id])
    assert f"Reading the log of device {device.id} failed" in caplog.text
