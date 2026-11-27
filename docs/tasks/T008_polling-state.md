# T008 — Polling, online/offline, event bus

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T006

## Context
The platform shows each device's live state from its own database, not by asking the board on every
page load. A poller per device reads `/state`, saves it when `rev` changes and tracks online/offline
and reboots. An in-process event bus publishes the changes: the history collector (T009) uses it now,
a Home Assistant adapter or live push can subscribe later.

## Objective
While the app runs, every registered device's `state`, `rev`, `online`, `last_seen_at` and `uptime_s`
follow the board within one poll interval; changes are published on the bus.

## Step 1 — Settings
`POLL_INTERVAL_S` (default 2.0, minimum 0.5), `POLL_OFFLINE_AFTER` (default 3 failed polls).

## Step 2 — Bus (`devices/bus.py`)
A minimal in-process pub/sub: `subscribe() -> asyncio.Queue`, `unsubscribe(q)`, `publish(event)`.
Events are small dataclasses: `StateChanged(device_pk, rev)`, `WentOnline`, `WentOffline`,
`Rebooted(device_pk, uptime_s)`. A full subscriber queue drops the oldest (a slow consumer never blocks
the poller). One instance assumed, as the rest of the app.

## Step 3 — Poller (`devices/poller.py`)
- A supervisor task started in the lifespan (next to the clean-up) and stopped on shutdown. It keeps
  one task per registered device: started on add, cancelled on remove, re-read every 30 s from the
  database so a device added or removed by another request is picked up.
- Each device task: `GET /state` every `POLL_INTERVAL_S` (through the T006 client, so it shares the
  per-host lock). `rev` changed → save `state`, `rev`, `uptime_s`, `last_seen_at`, publish
  `StateChanged`. Unchanged → only `last_seen_at`/`uptime_s` (one cheap UPDATE, no event).
  `uptime_s` lower than the last one → `Rebooted` and re-read `/info` (version, reset reason, entities
  may change after an update).
- `POLL_OFFLINE_AFTER` consecutive failures → `online=false`, `WentOffline`; the first answer after →
  `online=true`, `WentOnline`. While offline, poll every 10 s instead.
- A task's unexpected exception is logged (device id only) and the task restarted after a pause; it
  never kills the supervisor.
- Background work rule: this is the one exception to "only `core/scheduler.py`" (device I/O, one task
  per device). Document it in `platform-backend` → Background work and `platform-architecture`.

## Step 4 — API
`GET /api/devices/{id}` already returns the stored state (T006); add `online`, `last_seen_at`,
`uptime_s` if missing. No endpoint talks to the board here.

## Step 5 — Tests
With a fake client: rev change saves and publishes; unchanged rev no event; three failures → offline,
recovery → online; uptime backwards → `Rebooted` + `/info` re-read; add/remove starts/stops tasks; a
crashing task restarts; the bus drops the oldest on a full queue; lifespan starts and stops the
supervisor (no task left running). Use short intervals, no real sleeps longer than needed.

## DoD
1. `make lint-backend coverage-backend` pass (coverage ≥ 95 %).
2. Dev stack with `sim-garage-a` added: `POST /sim/button` on the simulator → within 3 s the
   device's state in `GET /api/devices/{id}` shows the door `opening`.
3. `POST /sim/offline {"seconds": 15}` → `online: false` within ~10 s, back to `true` after.
4. `POST /sim/power_cycle` → `Rebooted` logged and `reset_reason` updated to `power`.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-backend test-backend` | `tests.txt` | 0 failures |
| 2 | State follows | curl loop after `/sim/button` | `follow.txt` | `opening` ≤ 3 s |
| 3 | Offline | `/sim/offline` | `offline.txt` | false, then true |
| 4 | Reboot | `/sim/power_cycle` | `reboot.txt` | `reset_reason: power` |

## Files
| File | Action |
|------|--------|
| `platform/backend/app/devices/{bus,poller}.py` | Create |
| `platform/backend/app/main.py`, `core/config.py`, `devices/router.py`, `devices/service.py` | Modify |
| `platform/backend/tests/test_devices_poller.py`, `test_devices_bus.py` | Create |
| `.claude/skills/platform-backend/SKILL.md`, `platform-architecture/SKILL.md` | Modify |
| `platform/.env.example`, `platform/docs/configuration.md` | Modify |
