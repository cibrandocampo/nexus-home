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

## Implementation notes

- `devices/bus.py`: `Bus` (subscribe / unsubscribe / publish, queues of 256 that drop their oldest
  event when full), events `StateChanged`, `WentOnline`, `WentOffline`, `Rebooted`; one module-level
  `bus`, reset per test.
- `devices/poller.py`: `DevicePoller.poll_once` (one session per poll; events published after the
  commit) and `run`; `Supervisor` (one task per device id, `notify()` from the router after an add or
  remove, resync every 30 s, finished tasks restarted); `start` / `stop` in the lifespan next to the
  clean-up. Documented as the background-work exception in `platform-backend` and
  `platform-architecture`.
- Changes from the task text, found with the simulator:
  - A failed poll is retried after 0.5 s (`RETRY_S`) instead of the poll interval: with
    `DEVICE_TIMEOUT_S` 3, a silent board went offline after 16 s (longer than a 15 s outage); now
    about 12 s. Offline devices are polled every 5 s (`POLL_OFFLINE_INTERVAL_S`, planned 10 s).
  - A restart is detected when the uptime is below the expected one (last uptime + time since last
    seen − 5 s), not only when it goes down: a board that restarts while offline for longer than its
    previous uptime would otherwise be missed (T009's boots depend on it).
  - An answer without an integer `rev`, and a stored token that no longer decrypts, count as failed
    polls.
- DoD 2: `/sim/button` → `opening` in the platform within 1.1 s (`follow.txt`).
- DoD 3: `/sim/offline` 20 s → offline after ~12 s, online again ~5 s after the outage
  (`offline.txt`).
- DoD 4: `/restart` → `reset_reason: software`, then `/sim/power_cycle` → `power`, each logged as a
  restart (`reboot.txt`).
- Suite: 444 passed, coverage 100 %. Evidence: `docs/tasks/evidence/T008/`.

## QA — RETURNED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | `make lint-backend` | `docs/tasks/evidence/T008/qa/lint.txt` | PASS |
| 2 | `make coverage-backend`: 444 passed, 100 % | `docs/tasks/evidence/T008/qa/coverage.txt` | PASS |
| 3 | Simulator suite and lint (90 passed) | `docs/tasks/evidence/T008/qa/simulator.txt` | PASS |
| 4 | Frontend suite (128 passed) | `docs/tasks/evidence/T008/qa/frontend.txt` | PASS |
| 5 | Garage firmware host tests | `docs/tasks/evidence/T008/qa/firmware.txt` | PASS |
| 6 | DoD 2: `/sim/button` → `opening` in `GET /api/devices/5` after 0.58 s | `docs/tasks/evidence/T008/qa/follow.txt` | PASS |
| 7 | DoD 3: `/sim/offline` 15 s → `online: false` at +11.9 s, `true` at +17.2 s | `docs/tasks/evidence/T008/qa/offline.txt` | PASS |
| 8 | DoD 4: software restart → `software`, `/sim/power_cycle` → `power`, both logged as restarts | `docs/tasks/evidence/T008/qa/reboot.txt` | PASS |
| 9 | Review: state after a restart whose new `rev` matches the stored one | `docs/tasks/evidence/T008/qa/rev-reset.txt` | FAIL (B1) |
| 10 | Review: `/info` re-read after a restart, identity not checked | code review, `poller.py` | FAIL (B2) |

### Blockers
- **B1**: `platform/backend/app/devices/poller.py:37` `apply_state` (`if state["rev"] == device.rev: return False`)
  and `_answered`. A board's `rev` lives in RAM and starts again from 1 at every boot, so after a restart
  an equal `rev` does not mean an equal state. Expected: after a detected restart (and whenever `rev` is
  not trustworthy against the stored one) the answer is saved and `StateChanged` published. Found:
  stored rev 1 with the door `open` (a fresh boot), board offline 3 s, door closed by hand, power cycle;
  the board answers `rev 1, door closed`, the platform keeps `door open` (still wrong 10 s later, and it
  stays wrong until the next change on the board) — `rev-reset.txt`. Two power cuts in a row in the house
  give exactly this. Needs a test: restart with the same `rev` and a different state → saved + event.
- **B2**: `platform/backend/app/devices/poller.py:132` `_reread_info`: `apply_info(device, check_info(...))`
  never checks that `info["id"] == device.device_id`. `/info` and `/state` need no token, so if the
  address now belongs to another nexusHome board (DHCP lease handed over), the first uptime mismatch
  overwrites this row's name, model, version, mode, MAC and entities with the other board's. Expected:
  a different `id` is not applied (logged with both device ids, treated as a failed poll or a mismatch,
  your call), with a test. Device payloads are a boundary (qa.md: input validated at the boundaries).

### Observations (non-blocking)
- Restart detection misses a restart of a board whose uptime was under ~5 s (`REBOOT_SLACK_S`): in
  `rev-reset.txt` the second power cycle (uptime 2 s, then 3 s offline) logged no "restarted" line. Rare in
  practice; worth a line in the docstring, or fixed together with B1 (e.g. also treat `rev` lower than the
  stored one with uptime below the expected one as a restart).
- `poll_once` keeps its database session (and pooled connection) open across the board request, up to
  `DEVICE_TIMEOUT_S` plus any wait for the per-host lock. With the default pool (5 + 10) more than about
  15 slow or offline devices would starve API requests. Fine at the current scale; reading the row,
  closing the session, then writing in a second one would remove it.
- A device deleted while its poll is in flight ends in `StaleDataError` on the commit: logged as
  "failed unexpectedly" with a traceback, then the task ends 5 s later. Harmless, but noisy.
- `platform/docs/configuration.md` (`POLL_OFFLINE_AFTER`) says "offline after about 10 s"; measured
  ~12 s here and in the implementation notes.
- `devices/service.py` is listed as Modify in Files but was not needed (it already had `apply_info`,
  `check_info`, `client_for`); fine.

## Fixes after QA round 1

- **B1**: after a detected restart the `/state` answer is always saved and `StateChanged` published,
  whatever its `rev` (`apply_state(..., force=True)`): `rev` restarts at every boot. Test
  `test_after_a_restart_the_same_rev_is_still_a_new_state`; mutation (no `force`) fails it.
- **B2**: after a restart `/info` is checked against the stored device id. Another board's id → the
  poll counts as failed (`device_mismatch`, warning logged by device id) and neither its identity nor
  its state is saved; it ends offline after `POLL_OFFLINE_AFTER` polls. Test
  `test_another_board_at_the_address_never_takes_this_ones_identity`; mutation (no id check) fails it.
- O1: a restart also counts when the uptime simply went down (catches two restarts in a row with a
  tiny uptime). Test `test_a_restart_with_a_tiny_uptime_is_still_noticed`.
- O2: `poll_once` reads the device, closes the session, asks the board (`_ask`), then opens a new
  session to write: no database connection is held while a board answers.
- O3: a device removed during a poll ends the poller quietly (the second read finds no row). Test.
- O4: `configuration.md` says about 12 s.
- Suite: 448 passed, coverage 100 %.

## QA — APPROVED (round 2)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Round-1 B1: restart with the same `rev` and a different state is saved (unit test + simulator: two power cycles, door moved by hand while offline → platform `closed` like the board) | `docs/tasks/evidence/T008/qa/samerev-r2.txt`, `test_after_a_restart_the_same_rev_is_still_a_new_state` | PASS |
| 2 | Round-1 B2: another board's `/info` id after a restart → failed poll, no identity or state taken, warning logged | `test_another_board_at_the_address_never_takes_this_ones_identity` (reviewed: without the id check the name assertion fails) | PASS |
| 3 | `make lint-backend` | `docs/tasks/evidence/T008/qa/lint-r2.txt` | PASS |
| 4 | `make coverage-backend`: 448 passed, 100 % | `docs/tasks/evidence/T008/qa/coverage-r2.txt` | PASS |
| 5 | Simulator suite and lint | `docs/tasks/evidence/T008/qa/simulator-r2.txt` | PASS |
| 6 | Frontend suite | `docs/tasks/evidence/T008/qa/frontend-r2.txt` | PASS |
| 7 | Garage firmware host tests | `docs/tasks/evidence/T008/qa/firmware-r2.txt` | PASS |
| 8 | DoD 2: `/sim/button` → `opening` in `GET /api/devices/5` after 0.30 s | `docs/tasks/evidence/T008/qa/follow-r2.txt` | PASS |
| 9 | DoD 3: `/sim/offline` 15 s → `online: false` at +11.9 s, `true` at +17.1 s | `docs/tasks/evidence/T008/qa/offline-r2.txt` | PASS |
| 10 | DoD 4: software restart → `software`; `/sim/power_cycle` → `power` within 0.5 s; both logged "restarted" | `docs/tasks/evidence/T008/qa/reboot-r2.txt` | PASS |
| 11 | Round-1 observations O1–O4 (tiny uptime, no session held across the board request, removal during a poll, docs 12 s) | code review, tests | PASS |

### Observations (non-blocking)
- The identity check runs only when a restart is detected (`/state` carries no device id). Another board
  that takes the address with an uptime above the expected one is not detected, and after a detected
  restart with `/info` unreadable the `/state` answer is force-saved unverified. Acceptable now; T011/HA
  work could compare `/info` periodically or on every coming back online.
- `configuration.md` (`POLL_OFFLINE_AFTER`) says a failed read is "retried at once"; it is after 0.5 s
  (`RETRY_S`).

## After QA round 2

- Observation 1b: after a restart, a `/state` answer is no longer saved when `/info` cannot be read
  to confirm the board; the poll counts as failed and the next one retries (test
  `test_after_a_restart_nothing_is_saved_until_info_confirms_the_board`).
- Observation 1a (another board taking the address with a higher uptime than expected) is left:
  `/state` carries no id, and checking `/info` on every poll would double the requests to each board.
  T009 compares the `/log` boot and T011's settings use the token, which another board refuses.
- `configuration.md`: "retried after 0.5 s".
- `tests/test_devices_scan.py::test_one_scan_at_a_time` waited 0.05 s for the first scan to start and
  failed once under load; it now waits on an event set when the first scan probes.
- Suite: 448 passed, coverage 100 %; scan and poller tests 3 runs in a row green.
