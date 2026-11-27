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

## Implementation notes

- Models `DeviceBoot` (`started_at` = read time - uptime, refreshed on every read; `last_uptime_s`,
  `last_read_at`) and `DeviceEvent` (`t`, `at`, `event`, `source`, `reason`, `value`, `user_id` for
  T010); both cascade with their device. Migration `20261127_89631b8ade19_device_events`.
- `devices/history.py`:
  - `parse_log` (oldest first; malformed entries skipped, texts cut to the columns).
  - `new_entries`: a log that is not full holds everything since the boot, so what is stored is its
    exact prefix; a full log is matched by the longest stored suffix equal to its prefix. Limit
    (documented, tested): a full log of entries repeating in the same second is counted short,
    never twice.
  - Boots: same boot when the uptime did not go down and `started_at` moved by at most 10 s plus
    0.1 % of the time since the last read (the board's clock drifts); otherwise a new boot, which
    also catches a restart nobody saw.
  - `Collector`: subscribed to the bus before the poller starts (lifespan); reads on `StateChanged`
    and `Rebooted`, and every `LOG_READ_EVERY_S` per online device; never holds a database
    connection while the board answers.
- Retention: the hourly clean-up deletes events older than `EVENT_RETENTION_DAYS` and boots left
  without events, except each device's latest boot.
- API (`devices/events.py`, router): `GET /api/events` (filters `device`, `event` repeatable,
  `from`/`to` as aware ISO 8601, `to` exclusive) and `GET /api/devices/{id}/events`; paginated, newest
  first; each item names its device and the user (name only, never the email) or `null`.
- DoD 2: three door commands on the simulator → `door_opening`, `door_open` (stopped),
  `door_closing`, then `door_closed`; no duplicates two minutes later (`dedupe.txt`).
- DoD 3: `/sim/power_cycle` → a second boot; the first boot's events kept; the new boot's `boot` at
  +2 s of the power cycle (the simulator's restart time) and the light commands within 1.5 s of the
  request (`boots.txt`).
- Suite: 490 passed, coverage 100 %. Evidence: `docs/tasks/evidence/T009/`.

## QA — RETURNED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Backend lint and format | `docs/tasks/evidence/T009/qa/lint.txt` | PASS |
| 2 | Targeted tests, 3 runs | `docs/tasks/evidence/T009/qa/targeted-x3.txt` | PASS (42 x3) |
| 3 | Backend suite + coverage | `docs/tasks/evidence/T009/qa/coverage.txt` | PASS (490, 100 %) |
| 4 | Models vs migration | `docs/tasks/evidence/T009/qa/alembic-check.txt` | PASS |
| 5 | Simulator tests, frontend and simulator lint | `docs/tasks/evidence/T009/qa/other-suites2.txt` | PASS |
| 6 | Frontend tests | `docs/tasks/evidence/T009/qa/other-suites.txt`, `frontend-rerun.txt`, `frontend-rerun2.txt` | PASS (8 timeouts in the first run under load, see observations; 128/128 on the 2 re-runs) |
| 7 | Firmware host tests | `docs/tasks/evidence/T009/qa/firmware-host-tests.txt` | PASS |
| 8 | Production image build | `docs/tasks/evidence/T009/qa/image-build.txt` | PASS |
| 9 | DoD 2: three door commands, no duplicates 2 min later | `docs/tasks/evidence/T009/qa/dedupe.txt` | PASS (12 → 16 → 16, 0 duplicates) |
| 10 | DoD 3: power cycle, old boot kept, new times within 2 s | `docs/tasks/evidence/T009/qa/boots.txt` | PASS (3 boots; boot +0.46 s, light_on +0.67 s, light_off +0.76 s) |
| 11 | Device payload validation (`/log` entries out of the columns' range) | `docs/tasks/evidence/T009/qa/probe-out-of-range.txt` | FAIL |

### Blockers
- **B1**: `platform/backend/app/devices/history.py:417-434` (`parse_log`) — a device payload is not
  validated at the boundary: it only checks types, not ranges. Expected: entries (and `uptime_s`)
  outside what the board can send and the columns can hold are skipped / rejected as
  `device_bad_answer` (the firmware sends `t`, `value` and `uptime_s` as `uint32`: 0 to 2^32-1;
  `t` and `last_uptime_s` are `Integer`, so `t`/`uptime_s` must also fit int32, or the columns
  widen), and a test covers it. Found (probe with the real `collect()` against the fake board):
  `value = 2**63` and `t = 2**31` raise `DBAPIError` out of `collect`, `t = 10**12` raises
  `OverflowError` (timedelta), and in all three cases **nothing** of that read is stored, the good
  `boot` entry included; the read fails again on every later read until the bad entry leaves the
  board's 64-entry log, and the entries behind it are lost. `t = -5` is stored as is (an event
  before its boot).

### Observations (non-blocking)
- `tests/test_devices_history.py:125`: `assert len(new) <= 10` would also pass with `[]`; the case
  is deterministic (the longest overlap is 60, so 4 new), an exact assertion pins the documented limit.
- Step 2 says a `Rebooted` event opens a new boot; the code opens it from the uptime / start-time
  check and uses `Rebooted` only to trigger a read. Equivalent in behaviour and documented in the
  implementation notes.
- Retention edge: a boot whose 64 logged events are all older than `EVENT_RETENTION_DAYS` (a board up
  for over a year with no event) gets them re-inserted after each clean-up (stored tail empty, so the
  whole log looks new). Unlikely for a garage board; worth a comment or a guard on `at`.
- Frontend suite (untouched by T009): `ProfilePage.test.jsx` and `UsersPage.test.jsx` hit the 5 s
  test timeout in a run made right after the backend coverage run, with a firmware toolchain
  container also running (load 5.6 on 4 cores); two later runs passed 128/128. Timing-sensitive
  under load; worth its own `/fix`.

## Fixes after QA round 1

- **B1**: `parse_log` checks ranges as the board sends them (uint32): an entry is kept only with
  `0 <= t <= uptime_s` and `0 <= value <= 2**32 - 1`; an `uptime_s` outside `0..2**31 - 1` (the
  column) makes the answer `device_bad_answer`. One bad entry is skipped and the rest stored
  (`test_one_bad_entry_does_not_stop_the_history`, `test_entries_out_of_range_are_skipped`, the
  largest valid values fit). The poller stores an out-of-range `uptime_s` as null.
- O1: `test_a_full_log_of_identical_toggles_is_counted_short_never_twice` asserts the exact result
  (the last 4 entries).
- O3: entries older than `EVENT_RETENTION_DAYS` are left out of the fetched log before comparing it
  with what is stored, so a board up for longer than the retention does not get them re-inserted
  after each clean-up (test; mutation without the filter fails it).
- O2 (a `Rebooted` event only triggers a read; the boot comes from the log) is by design, noted.
- The frontend timeouts seen by QA under load are not part of this task; they are noted for a later
  `/fix` if they come back.
- Suite: 503 passed, coverage 100 %.

## QA — RETURNED (round 2)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Backend lint and format | `docs/tasks/evidence/T009/qa/r2/lint.txt` | PASS |
| 2 | Backend suite + coverage | `docs/tasks/evidence/T009/qa/r2/coverage.txt` | PASS (503, 100 %) |
| 3 | B1 re-check: numeric ranges in `/log` (`value` 2^63, 2^32, -1, 1.5; `t` 2^31, 10^12, -5, > uptime) through the real `collect()` | `docs/tasks/evidence/T009/qa/r2/probe-payloads.txt` | PASS (bad entry skipped, the good `boot` entry stored; `value` 2^32-1 and `t` = uptime kept) |
| 4 | Device payload validation: text fields (`event` with `\u0000`, `source` with a lone surrogate `\ud800`) | `docs/tasks/evidence/T009/qa/r2/probe-payloads.txt` | FAIL |
| 5 | Other suites, image build, DoD 2-3 on the dev stack | — | Not run (phase failed; round 1 passed them, re-run after the fix) |

### Blockers
- **B2**: `platform/backend/app/devices/history.py:56-66` (`parse_log`) — the B1 fix validates the
  numbers but not the texts, and a bad text has the same effect B1 described. Expected: an entry
  whose `event` / `source` / `reason` the columns cannot hold is skipped (or the text cleaned), the
  rest of the read stored, with a test. Found: `/log` is parsed with `response.json()`, which turns
  the JSON escapes `\u0000` and `\ud800` into a NUL and a lone surrogate; then `collect()` raises
  `DBAPIError` (`invalid byte sequence for encoding "UTF8": 0x00`) or `UnicodeEncodeError`
  (`surrogates not allowed`), **nothing** of that read is stored (the good `boot` entry included:
  `stored: []`), and every later read fails the same way until the entry leaves the board's
  64-entry log. A simple rule that covers both: keep only texts that are printable ASCII (the
  firmware's event names are identifiers), or at least reject `\x00` and anything that does not
  encode to UTF-8.

### Observations (non-blocking)
- B1 (numbers) is fixed and covered (`test_entries_out_of_range_are_skipped`,
  `test_the_largest_values_a_board_sends_fit`, `test_an_uptime_out_of_range_is_not_a_log`,
  `test_one_bad_entry_does_not_stop_the_history`); O1 and O3 are addressed.
- `Collector.step`: when `read()` raises for the device of a `StateChanged`, the periodic `due()`
  reads of the other devices are skipped for that iteration (and one raising device in the `due()`
  loop skips the ones after it). `last_read` is set before the read, so it recovers on the next
  iteration; it stops mattering once B2 is fixed, but catching per device would make the loop
  independent of any one board.
- Same class, outside T009: the poller stores the board's state in a JSONB column, which also
  rejects `\u0000`; worth checking under T008 / a `/fix`.

## Fixes after QA round 2

- **B2**: `parse_log` keeps an entry only when `event`, `source` and `reason` are firmware identifiers
  (`^[a-z0-9_]{1,32}$`): a NUL, a lone surrogate, spaces or capitals skip that entry and the rest is
  stored (`test_one_entry_with_an_unstorable_text_does_not_stop_the_history`, with `\u0000` and
  `\ud800` sent as raw JSON; `test_entries_whose_names_are_not_identifiers_are_skipped`).
- Observation (T008, the poller's JSONB): the device client now refuses as `device_bad_answer` any
  answer whose strings the database cannot hold (`client.storable`: no NUL, no lone surrogate),
  except `/log`, which is checked entry by entry so that one bad entry does not hide the others.
- Observation: `Collector.read` catches a failure per device (logged with the device id); the other
  devices are still read in the same step (test).
- Live: a `light/toggle` on sim-garage-a appears in the device's history within 4 s.
- Suite: 515 passed, coverage 100 %.

## QA — APPROVED (round 3)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | B2 re-check: names must be firmware identifiers (`\u0000`, `\ud800` as raw JSON through `collect()`, spaces, capitals, empty, 33 chars); firmware and simulator only send identifiers (`none` for no reason) | `tests/test_devices_history.py` (read), `docs/tasks/evidence/T009/qa/r3/targeted-x3.txt` | PASS |
| 2 | Lint of every platform stack (backend, frontend, simulator, e2e) | `docs/tasks/evidence/T009/qa/r3/lint.txt` | PASS |
| 3 | Targeted tests (history + client), 3 runs | `docs/tasks/evidence/T009/qa/r3/targeted-x3.txt` | PASS (87 x3) |
| 4 | Backend suite + coverage | `docs/tasks/evidence/T009/qa/r3/coverage.txt` | PASS (515, 100 %) |
| 5 | Models vs migration (`alembic check`, head `89631b8ade19`) | `docs/tasks/evidence/T009/qa/r3/alembic-check.txt` | PASS |
| 6 | Frontend suite | `docs/tasks/evidence/T009/qa/r3/frontend.txt` | PASS (128/128) |
| 7 | Simulator suite (contract included) | `docs/tasks/evidence/T009/qa/r3/simulator.txt` | PASS (90, 99 %) |
| 8 | Firmware host tests (firmware untouched by T009, so no firmware build) | `docs/tasks/evidence/T009/qa/r3/firmware-host-tests.txt` | PASS |
| 9 | Production image build | `docs/tasks/evidence/T009/qa/r3/image-build.txt` | PASS |
| 10 | DoD 2: open / stop / close on sim-garage-a, then 125 s of polling | `docs/tasks/evidence/T009/qa/r3/dedupe.txt` | PASS (`door_opening`, `door_open` stopped, `door_closing`, `door_closed`: 4 → 4, 0 duplicates, the same rows) |
| 11 | DoD 3: `/sim/power_cycle`, then light on / off | `docs/tasks/evidence/T009/qa/r3/boots.txt` | PASS (new boot 4; boot 3's 11 events kept; boot +0.12 s, light_on +0.31 s, light_off +0.38 s of the requests) |

### Observations (non-blocking)
- The B2 integration test injects the bad text in `event` only; `source` and `reason` go through the
  same `NAME` check and are covered by the unit cases (`source="\ud800"`, `reason="Sensor"`).
- Event times land up to 0.7 s before the request (`t` is whole seconds); within the DoD's 2 s.
