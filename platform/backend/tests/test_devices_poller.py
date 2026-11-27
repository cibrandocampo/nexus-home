import asyncio
import logging

import pytest

from app.core.config import get_settings
from app.core.db import get_sessionmaker
from app.devices import poller
from app.devices.bus import Rebooted, StateChanged, WentOffline, WentOnline, bus
from app.devices.crypto import encrypt_token
from app.devices.models import Device
from app.devices.poller import DevicePoller, Supervisor
from tests.fakeboard import garage_state

HOST = "10.1.3.50"


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


@pytest.fixture
def events():
    return bus.subscribe()


def drain(queue) -> list:
    out = []
    while not queue.empty():
        out.append(queue.get_nowait())
    return out


async def reload(db, device) -> Device:
    pk = device.id  # read before expiring: an expired attribute would need a lazy load
    db.expire_all()
    return await db.get(Device, pk)


async def until(condition, within_s=3.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + within_s
    while not await condition():
        assert loop.time() < deadline, "condition not met in time"
        await asyncio.sleep(0.01)


# ---- one poll ----


async def test_a_new_rev_is_saved_and_published(db, lan, device, events):
    lan.boards[HOST].state = garage_state(rev=7, uptime_s=120, door="opening")

    delay = await DevicePoller(device.id).poll_once()

    assert delay == get_settings().poll_interval_s
    row = await reload(db, device)
    assert (row.rev, row.uptime_s, row.state["door"]["state"]) == (7, 120, "opening")
    assert row.last_seen_at is not None
    assert drain(events) == [StateChanged(device.id, 7)]


async def test_the_same_rev_refreshes_the_counters_without_an_event(db, lan, device, events):
    p = DevicePoller(device.id)
    await p.poll_once()
    drain(events)
    first_seen = (await reload(db, device)).last_seen_at
    board = lan.boards[HOST]
    board.state = {**board.state, "uptime_s": 103, "light_level": 999}  # level drifts, rev does not

    await p.poll_once()

    row = await reload(db, device)
    assert row.state["light_level"] == 999  # counters and readings move without a new rev
    assert (row.uptime_s, row.last_seen_at > first_seen) == (103, True)
    assert drain(events) == []


async def test_three_failures_make_it_offline_and_one_answer_brings_it_back(
    db, lan, device, events
):
    p = DevicePoller(device.id)
    lan.boards[HOST].unreachable = True

    delays = [await p.poll_once() for _ in range(3)]

    settings = get_settings()
    assert delays == [poller.RETRY_S] * 2 + [settings.poll_offline_interval_s]
    assert (await reload(db, device)).online is False
    assert drain(events) == [WentOffline(device.id)]
    await p.poll_once()
    assert drain(events) == []  # published once

    lan.boards[HOST].unreachable = False
    assert await p.poll_once() == settings.poll_interval_s
    assert (await reload(db, device)).online is True
    assert drain(events) == [WentOnline(device.id), StateChanged(device.id, 1)]


async def test_failures_count_from_the_last_answer(db, lan, device):
    p = DevicePoller(device.id)
    board = lan.boards[HOST]
    for unreachable in (True, True, False, True, True):
        board.unreachable = unreachable
        await p.poll_once()

    assert (await reload(db, device)).online is True


async def test_the_offline_threshold_comes_from_the_settings(db, lan, device, monkeypatch):
    monkeypatch.setenv("POLL_OFFLINE_AFTER", "1")
    get_settings.cache_clear()
    try:
        lan.boards[HOST].unreachable = True
        await DevicePoller(device.id).poll_once()
    finally:
        get_settings.cache_clear()

    assert (await reload(db, device)).online is False


@pytest.mark.parametrize("state", [{"uptime_s": 5}, {"rev": "7"}])
async def test_an_answer_without_a_rev_counts_as_a_failure(db, lan, device, state):
    lan.boards[HOST].state = state
    p = DevicePoller(device.id)

    for _ in range(3):
        await p.poll_once()

    assert (await reload(db, device)).online is False


async def test_a_stored_token_that_no_longer_decrypts_counts_as_a_failure(db, lan, device):
    device.token_encrypted = "not-fernet"
    await db.commit()
    p = DevicePoller(device.id)

    for _ in range(3):
        await p.poll_once()

    assert (await reload(db, device)).online is False


async def test_uptime_going_back_is_a_reboot_and_info_is_read_again(db, lan, device, events):
    board = lan.boards[HOST]
    p = DevicePoller(device.id)
    board.state = garage_state(rev=9, uptime_s=5000)
    await p.poll_once()
    drain(events)
    board.state = garage_state(rev=1, uptime_s=4)
    board.sw_version = "2.0.7"

    await p.poll_once()

    assert drain(events) == [Rebooted(device.id, 4), StateChanged(device.id, 1)]
    row = await reload(db, device)
    assert (row.sw_version, row.uptime_s, row.rev) == ("2.0.7", 4, 1)


async def test_after_a_restart_nothing_is_saved_until_info_confirms_the_board(
    db, lan, device, events, caplog
):
    import httpx

    board = lan.boards[HOST]
    p = DevicePoller(device.id)
    board.state = garage_state(rev=9, uptime_s=5000)
    await p.poll_once()
    board.state = garage_state(rev=1, uptime_s=4)
    board.raw["info"] = httpx.Response(500, text="busy")

    with caplog.at_level(logging.INFO):
        await p.poll_once()

    assert "Could not re-read /info of device garage-abc123" in caplog.text
    assert (await reload(db, device)).rev == 9  # whose state? not saved yet
    drain(events)
    del board.raw["info"]

    await p.poll_once()  # the restart is seen again, /info answers now

    assert drain(events) == [Rebooted(device.id, 4), StateChanged(device.id, 1)]
    assert (await reload(db, device)).rev == 1


async def test_a_removed_device_ends_its_poller(db, device):
    await db.delete(device)
    await db.commit()

    assert await DevicePoller(device.id).poll_once() is None


async def test_the_poll_loop_survives_an_unexpected_error(monkeypatch, caplog):
    calls = []

    async def poll_once(self):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        return None

    monkeypatch.setattr(DevicePoller, "poll_once", poll_once)
    monkeypatch.setattr(poller, "RESTART_PAUSE_S", 0)

    await DevicePoller(1).run()

    assert len(calls) == 2
    assert "Polling device 1 failed unexpectedly" in caplog.text


async def test_the_loop_waits_the_returned_delay(monkeypatch):
    delays = iter([0.01, None])

    async def poll_once(self):
        return next(delays)

    monkeypatch.setattr(DevicePoller, "poll_once", poll_once)

    await asyncio.wait_for(DevicePoller(1).run(), 1)


# ---- supervisor ----


async def test_the_supervisor_follows_the_registry(db, lan, device, monkeypatch):
    monkeypatch.setenv("POLL_INTERVAL_S", "0.5")
    get_settings.cache_clear()
    sup = Supervisor()
    task = asyncio.create_task(sup.run())
    try:
        await until(lambda: _has(sup, device.id))
        await until(lambda: _rev_saved(db, device))

        await db.delete(device)
        await db.commit()
        sup.notify()
        await until(lambda: _empty(sup))
    finally:
        task.cancel()
        await sup.stop()
        get_settings.cache_clear()


async def _has(sup, pk):
    return pk in sup.tasks


async def _empty(sup):
    return not sup.tasks


async def _rev_saved(db, device):
    return (await reload(db, device)).rev == 1


async def test_a_finished_device_task_is_started_again(db, device):
    sup = Supervisor()
    sup.tasks[device.id] = asyncio.create_task(asyncio.sleep(0))
    await asyncio.sleep(0.01)

    await sup.sync()

    try:
        assert not sup.tasks[device.id].done()
    finally:
        await sup.stop()


async def test_the_supervisor_survives_a_database_error(monkeypatch, caplog):
    sup = Supervisor()
    calls = []

    async def sync():
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("db down")

    monkeypatch.setattr(sup, "sync", sync)
    monkeypatch.setattr(poller, "RESYNC_S", 0.01)
    task = asyncio.create_task(sup.run())
    await until(lambda: _calls(calls, 2))
    task.cancel()
    await sup.stop()

    assert "Device supervisor could not read the registry" in caplog.text


async def _calls(calls, n):
    return len(calls) >= n


async def test_start_and_stop_leave_no_task_running(db, device):
    task = poller.start()
    await until(lambda: _has(poller._supervisor, device.id))
    poller.notify()  # running: wakes the supervisor (a resync, nothing changes)
    await asyncio.sleep(0.05)
    device_tasks = list(poller._supervisor.tasks.values())
    assert len(device_tasks) == 1

    await poller.stop(task)

    assert task.done() and all(t.done() for t in device_tasks)
    assert poller._supervisor is None
    poller.notify()  # not running: a no-op


async def test_adding_and_removing_through_the_api_notifies_the_supervisor(
    client, lan, make_user, monkeypatch
):
    from app.core.security import create_access_token
    from app.users.models import Role
    from tests.helpers import auth

    lan.add(HOST)
    admin = await make_user("admin@example.com", role=Role.admin)
    headers = auth(create_access_token(admin.id, "admin"))
    notified = []
    monkeypatch.setattr(poller, "notify", lambda: notified.append(1))

    pk = (
        await client.post(
            "/api/devices", json={"host": HOST, "token": "board-token-1"}, headers=headers
        )
    ).json()["id"]
    await client.delete(f"/api/devices/{pk}", headers=headers)

    assert notified == [1, 1]


async def test_a_restart_while_offline_is_noticed_even_if_uptime_grew(db, lan, device, events):
    from datetime import timedelta

    board = lan.boards[HOST]
    p = DevicePoller(device.id)
    board.state = garage_state(rev=3, uptime_s=100)
    await p.poll_once()
    row = await reload(db, device)
    row.last_seen_at -= timedelta(hours=1)  # then an hour offline; it restarted 50 min ago
    await db.commit()
    drain(events)
    board.state = garage_state(rev=1, uptime_s=3000)

    await p.poll_once()

    assert drain(events)[0] == Rebooted(device.id, 3000)


async def test_normal_polls_are_not_restarts(db, lan, device, events):
    from datetime import timedelta

    board = lan.boards[HOST]
    p = DevicePoller(device.id)
    board.state = garage_state(rev=3, uptime_s=100)
    await p.poll_once()
    row = await reload(db, device)
    row.last_seen_at -= timedelta(seconds=60)
    await db.commit()
    drain(events)
    board.state = garage_state(rev=4, uptime_s=158)  # 2 s behind the wall clock: within the slack

    await p.poll_once()

    assert drain(events) == [StateChanged(device.id, 4)]


async def test_after_a_restart_the_same_rev_is_still_a_new_state(db, lan, device, events):
    # rev lives in the board's RAM: every boot starts again from 1.
    board = lan.boards[HOST]
    p = DevicePoller(device.id)
    board.state = garage_state(rev=1, uptime_s=50, door="open")
    await p.poll_once()
    drain(events)
    board.state = garage_state(rev=1, uptime_s=2, door="closed")  # restarted, door closed by hand

    await p.poll_once()

    assert drain(events) == [Rebooted(device.id, 2), StateChanged(device.id, 1)]
    assert (await reload(db, device)).state["door"]["state"] == "closed"


async def test_a_restart_with_a_tiny_uptime_is_still_noticed(db, lan, device, events):
    board = lan.boards[HOST]
    p = DevicePoller(device.id)
    board.state = garage_state(rev=1, uptime_s=3)  # just booted
    await p.poll_once()
    drain(events)
    board.state = garage_state(rev=1, uptime_s=1)  # and again

    await p.poll_once()

    assert drain(events)[0] == Rebooted(device.id, 1)


async def test_another_board_at_the_address_never_takes_this_ones_identity(
    db, lan, device, events, caplog
):
    board = lan.boards[HOST]
    p = DevicePoller(device.id)
    board.state = garage_state(rev=9, uptime_s=5000)
    await p.poll_once()
    drain(events)
    before = await reload(db, device)
    name, state = before.name, before.state
    board.device_id, board.name, board.sw_version = "garage-ffffff", "Shed", "9.9.9"
    board.state = garage_state(rev=1, uptime_s=4, door="open")

    for _ in range(3):
        await p.poll_once()

    row = await reload(db, device)
    assert (row.device_id, row.name, row.sw_version) == ("garage-abc123", name, "")
    assert row.state == state  # the other board's state is not saved either
    assert row.online is False  # counts as failed polls
    assert drain(events) == [WentOffline(device.id)]
    assert "Another device answers at the address of garage-abc123" in caplog.text


async def test_a_device_removed_during_a_poll_ends_quietly(db, lan, device, monkeypatch, caplog):
    from app.devices import poller as module

    real_ask = module._ask

    async def ask_then_remove(snapshot):
        answer = await real_ask(snapshot)
        async with get_sessionmaker()() as other:
            await other.delete(await other.get(Device, snapshot.id))
            await other.commit()
        return answer

    monkeypatch.setattr(module, "_ask", ask_then_remove)

    assert await DevicePoller(device.id).poll_once() is None
    assert "Traceback" not in caplog.text
