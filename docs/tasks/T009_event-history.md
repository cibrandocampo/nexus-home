# T009 — Event history

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T008

## Context
A board keeps its last 64 events in RAM, with times in seconds since boot, and loses them on every
restart. The platform collects them, gives them an absolute time and keeps them for a year.

## Objective
Every event a board logs while the platform runs is stored once, with its absolute UTC time, and can
be listed per device or globally with filters.

## Step 1 — Model and migration
`DeviceEvent`: `id`, `device_pk` (FK, cascade delete), `boot_id` (see below), `t` (board uptime
seconds), `at` (absolute UTC, indexed with `device_pk`), `event`, `source`, `reason`, `value`, `user_id`
(nullable FK, `SET NULL`: filled by T010 for commands sent through the platform). `DeviceBoot`:
`id`, `device_pk`, `started_at` (`poll time − uptime_s`), `reset_reason`. Settings
`EVENT_RETENTION_DAYS` (default 365), `LOG_READ_EVERY_S` (default 60).

## Step 2 — Collector (`devices/history.py`)
- Subscribes to the bus: on `StateChanged` (and at least every `LOG_READ_EVERY_S` per online device)
  reads `GET /log` (`uptime_s` + `events` newest first).
- Boots: the current boot is the device's last `DeviceBoot`; a `Rebooted` event, or a log whose
  `uptime_s` is lower than the last read, opens a new one with `started_at = now − uptime_s`.
- New entries: the fetched log, oldest first, overlaps the stored tail of the current boot; the
  longest suffix of the stored entries (compared on `t, event, source, reason, value`) that equals a
  prefix of the fetched list is skipped, the rest is inserted. No overlap (more than 64 events since
  the last read) → all inserted, and a warning logged with the device id. Absolute time:
  `at = boot.started_at + t`.
- The collector never blocks the poller (its own task; reads go through the shared per-host lock).

## Step 3 — Retention
The `core/scheduler.py` clean-up deletes events older than `EVENT_RETENTION_DAYS` (and boots with no
events left), with `_skip_locked` like the rest.

## Step 4 — API
`GET /api/devices/{id}/events` and `GET /api/events` (`RequireUser`), paginated, newest first,
filters `device` (global list), `event` (repeatable), `from`, `to` (ISO 8601). Each item: `at`,
`event`, `source`, `reason`, `value`, device `{id, name}` and `user` `{id, name}` or `null`.

## Step 5 — Tests
Overlap logic (no new, some new, all new, roll-over without overlap, identical repeated events such
as 70 light toggles in the same second), boot change, absolute times, retention, filters, pagination,
roles. The collector with a fake client and a real bus.

## DoD
1. `make lint-backend coverage-backend` pass (coverage ≥ 95 %).
2. Dev stack: three door commands on the simulator (`curl` to the simulator) → exactly those events in
   `GET /api/devices/{id}/events`, no duplicates after 2 minutes of polling.
3. `POST /sim/power_cycle`, then more commands: the old boot's events stay, the new ones follow with
   correct absolute times (within 2 s of the request time).

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-backend test-backend` | `tests.txt` | 0 failures |
| 2 | No duplicates | curl events twice, 2 min apart | `dedupe.txt` | same count, matching |
| 3 | Reboot | power_cycle + commands | `boots.txt` | both boots, times ±2 s |

## Files
| File | Action |
|------|--------|
| `platform/backend/app/devices/history.py`, `models.py`, `router.py`, `schemas.py` | Create / modify |
| `platform/backend/app/core/scheduler.py`, `core/config.py`, `main.py` | Modify |
| `platform/backend/alembic/versions/<date>_device_events.py` | Create |
| `platform/backend/tests/test_devices_history.py` | Create |
| `platform/.env.example`, `platform/docs/configuration.md` | Modify |
