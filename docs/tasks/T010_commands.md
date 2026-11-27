# T010 — Commands and their audit

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T009

## Context
Users (`user`+) operate the door and the light from the platform. The board's history only says
`source: api`; the platform knows who sent it.

## Objective
`POST /api/devices/{id}/entities/{entity}/{command}` sends a command to the board and answers with the
new state; every command is recorded with its user, and the history shows that user on the event it
caused.

## Step 1 — Model and migration
`DeviceCommand`: `id`, `device_pk` (FK cascade), `user_id` (FK `SET NULL`), `entity`, `command`,
`params` (JSONB), `at`, `result` (`ok`, `noop` or the error code), `status` (HTTP status from the board
or null when unreachable).

## Step 2 — Endpoint
- `RequireUser`. The entity must be in the device's stored entities and the command in its
  `commands` list (else 404 `entity_not_found` / `command_not_found`). Params: only `duration` for
  `light/on` (integer 0–86400, validated by the platform too).
- Sends `POST /api/v1/<entity>/<command>` with the stored token. On success saves the returned state
  (same path as the poller: `rev`, `state`, `last_seen_at`) and answers `{result, state}`.
- Board errors pass through with their code and the matching status: `door_busy` → 409,
  `invalid_duration` → 400; `unauthorized` → 409 `device_token_invalid` (the stored token is stale; the
  user cannot fix it, an admin can); unreachable → 502 `device_unreachable`; offline device → 409
  `device_offline` without trying.
- Every call is recorded in `DeviceCommand`, failures included. Rate limit per user (e.g. 30/min).

## Step 3 — Attribution in the history
When the collector stores an event with `source: api` whose type follows from a command (door events
for `door/*`, light events for `light/*`), it sets `user_id` from the latest successful
`DeviceCommand` on that device and entity within 5 s before the event's `at` and not yet attributed
(one command → at most the events it caused: the door's next state change and the auto light).
Document the rule; boards with exact correlation (a command id in the log) can replace it later.

## Step 4 — Tests
Each command against a fake board; pass-through of `door_busy`, `invalid_duration`; stale token;
unreachable; offline; unknown entity/command; role `none` 403; anonymous 401; audit rows for success
and failure; attribution (right user, not an older command, not a button press, light auto event).

## DoD
1. `make lint-backend coverage-backend` pass (coverage ≥ 95 %).
2. Dev stack: `door/open` through the platform as a `user` → 200 with `opening`; an immediate
   `door/close` → 409 `door_busy`; the history shows `door_opening · api · <that user>`.
3. Bench board (`garage-33ad84`, free to use) added to the dev stack: `light/on?duration=10` through the
   platform turns its light relay on and the history shows the user. Never the production board.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-backend test-backend` | `tests.txt` | 0 failures |
| 2 | Simulator | curl as a user | `commands.txt` | 200, 409, attributed event |
| 3 | Bench board | curl as a user | `bench.txt` | light on 10 s, attributed |

## Files
| File | Action |
|------|--------|
| `platform/backend/app/devices/commands.py`, `models.py`, `router.py`, `history.py` | Create / modify |
| `platform/backend/alembic/versions/<date>_device_commands.py` | Create |
| `platform/backend/tests/test_devices_commands.py` | Create |
| `.claude/skills/platform-api/SKILL.md` | Modify (codes) |

## Implementation notes

- `DeviceCommand` (migration `20261127_10a191ed114c_device_commands`): device, user (`SET NULL`),
  entity, command, params, time, result (`ok`, `noop`, or the error code: the board's own code when
  it answered, the platform's otherwise) and the board's HTTP status (null when it did not answer).
- `devices/commands.py` `send`: the entity and command must be in the stored `/info` entities
  (404 `entity_not_found` / `command_not_found`); only `light/on` takes `duration` (integer 0–86400,
  strict; others → 422 `invalid_params`); an offline device is not tried (409 `device_offline`).
  Board `door_busy` → 409, `invalid_duration` → 400, `unauthorized` → 409 `device_token_invalid`, no
  answer → 502 `device_unreachable`, anything else → 502 `device_error`. On success the returned state
  is saved and `StateChanged` published, so the history reads the log right away. Rate limit
  `COMMAND_USER` 30 per minute per user.
- `apply_state` now saves only a higher `rev` (or any after a restart): a poll that started before a
  command answered must not put the older state back.
- Attribution (`attribute`, called by the collector before adding the new rows):
  - events the command caused right away (`door_opening`, `door_closing`, a stop's `door_open` /
    `door_closed` with reason `stopped`, `light_on`, `light_off`) with `source: api` take the user of
    the latest successful command on that entity from 5 s before to 2 s after the event;
  - a movement's end (`door_open` at the end of the travel, `door_closed` by the sensor,
    `close_failed`) takes the user of the movement's start, also across two reads;
  - the auto light, the button, the sensor and commands from elsewhere (the board's own page) stay
    without a user.
- DoD 2: as a `user` (Ana Dev, created in the dev stack), `door/open` → 200 `opening`, an immediate
  `door/close` → 409 `door_busy`; the history shows `door_opening` and `door_open` (travel end) with
  "Ana Dev"; light events sent straight to the simulator have no user; both commands audited
  (`commands.txt`).
- DoD 3: **NEEDS USER** — the bench board is unplugged (no `/dev/ttyACM0`, 10.1.3.114 silent).
- Suite: 550 passed, coverage 100 %. Evidence: `docs/tasks/evidence/T010/`.

## QA — RETURNED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Backend lint and format | `docs/tasks/evidence/T010/qa/lint-backend.txt` | PASS |
| 2 | Backend suite and coverage (550 passed, 100 %) | `docs/tasks/evidence/T010/qa/coverage-backend.txt` | PASS |
| 3 | Models match migrations (`alembic check`, head `10a191ed114c`) | `docs/tasks/evidence/T010/qa/alembic.txt` | PASS |
| 4 | All linters (`make lint`) | `docs/tasks/evidence/T010/qa/lint-all.txt` | PASS |
| 5 | Frontend and simulator suites | `docs/tasks/evidence/T010/qa/test-frontend.txt`, `test-simulator.txt` | PASS |
| 6 | Firmware host tests (garage) | `docs/tasks/evidence/T010/qa/firmware-test.txt` | PASS |
| 7 | DoD 2: `door/open` as `user` → 200 `opening`, immediate `door/close` → 409 `door_busy`, history `door_opening · api · Ana Dev`; 401 anonymous, 404 entity/command, 422 params | `docs/tasks/evidence/T010/qa/commands.txt` | PASS |
| 8 | Step 3: a command attributes only the events it caused ("not yet attributed") | `docs/tasks/evidence/T010/qa/attribution-probe.txt` | FAIL |
| 9 | DoD 3: bench board `light/on?duration=10` | — (bench board unplugged) | NEEDS USER |

### Blockers
- **B1**: `platform/backend/app/devices/commands.py` `attribute` (the `select(DeviceCommand.user_id)` query) —
  Step 3 requires the command to be "not yet attributed (one command → at most the events it caused)";
  the query takes the latest successful command in the window with no check that it was already used,
  so one command names its user on every `source: api` event of that entity inside the window,
  including ones sent by another API client (the board's own page, Home Assistant). Evidence
  `attribution-probe.txt`: Ana's `light/on` through the platform (audit row 7, the only platform command),
  then `light/off` straight to the simulator's `/api/v1` 1 s later → the history shows both `light_on`
  and `light_off` with user "Ana Dev"; expected `light_off` with `user: null`. Same flaw for the door:
  `door/open` by a user followed within the window by a stop from the board's page gives the
  `door_open`/`stopped` event to that user. The implementation notes' claim "commands from elsewhere
  (the board's own page) stay without a user" is false inside the window. Needs: consume a command
  once per immediate event (e.g. exclude commands already matched by a stored or earlier-in-batch event,
  or store the matched command on the event), plus tests for "a second api event in the window names
  nobody" (light and door stop).

### Observations
- `commands.send` publishes `StateChanged` before `_record` commits the `DeviceCommand`; the collector
  only reads it after a board round-trip, so it works in practice, but publishing after the commit
  removes the race with attribution.
- The window is 5 s before to 2 s after the event, not "within 5 s before" as in Step 3; documented in
  the docstring and notes, acceptable.
- `apply_state` now refuses `rev <= stored`: if the board restarted and the first contact after it is a
  command (before the poller sees the reboot), the answer returns the stale stored state until the
  next poll forces it.
- Nits: `DeviceCommand.result.in_(("ok",))` is `== "ok"`; `test_a_board_that_does_not_answer` calls
  `audit()` twice; `test_commands_through_the_api_end_up_in_the_history` imports `collect` inside the
  function.

## Fixes after QA round 1

- **B1**: a command is used up by the events it causes. `DeviceCommand` gains `credited` and `used`
  (in the same migration, not yet on main). `EXPECTS` lists, per command, the events it can cause
  right away and its target event: `door/open` → `door_opening` (and, for a reversal, the
  `door_closing` and stopped `door_open` before it), `door/close` the mirror, `door/stop` → a stopped
  `door_open`/`door_closed`, `light/on` → `light_on`, `light/off` → `light_off`, the toggles either.
  An immediate `source: api` event takes the oldest unused successful command on its entity in the
  window that can cause it; the target (or a third credit) uses it up. Tests: an api `light_off`
  from elsewhere one second after a platform `light/on` and a stop from elsewhere after an open stay
  without a user; a reversal credits its three events; two users in a row; a used command stays used
  across reads; at most three credits; a pending command does not take an event it cannot cause.
  Reproduced on the dev stack as QA did: `light_on` "Ana Dev", the simulator's direct `light_off`
  null (`elsewhere.txt`).
- `send` publishes `StateChanged` after the audit row is saved, so the collector can credit it.
- Suite: 557 passed, coverage 100 %.

## QA — APPROVED (round 2)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Round 1 B1: one command credits only the events it caused | `docs/tasks/evidence/T010/qa/r2/dev-stack-probe.txt`, `coverage-backend.txt` | PASS |
| 2 | All linters (`make lint`) | `docs/tasks/evidence/T010/qa/r2/lint-all.txt` | PASS |
| 3 | Backend suite and coverage (557 passed, 100 %) | `docs/tasks/evidence/T010/qa/r2/coverage-backend.txt` | PASS |
| 4 | Models match migrations (`alembic check`, head `10a191ed114c`, `credited`/`used` in it) | `docs/tasks/evidence/T010/qa/r2/alembic.txt` | PASS |
| 5 | Frontend and simulator suites | `docs/tasks/evidence/T010/qa/r2/test-frontend.txt`, `test-simulator.txt` | PASS |
| 6 | Firmware host tests (garage) | `docs/tasks/evidence/T010/qa/r2/firmware-test.txt` | PASS |
| 7 | DoD 2: `door/open` as `user` → 200 `opening`, immediate `door/close` → 409 `door_busy`, history `door_opening · api · Ana Dev`, both audited | `docs/tasks/evidence/T010/qa/r2/dev-stack-probe.txt` | PASS |
| 8 | B1 repro on the dev stack: stop straight to the simulator 2 s after the platform's open → `door_open`/`stopped` user null; `light_off` straight to the simulator 1 s after the platform's `light/on` → user null; the platform's own events keep "Ana Dev"; audit rows `credited=1, used=t` | `docs/tasks/evidence/T010/qa/r2/dev-stack-probe.txt` | PASS |
| 9 | DoD 3: bench board `light/on?duration=10` | — (bench board unplugged) | NEEDS USER |

### Observations
- A successful command whose target event never comes (e.g. `door/stop` answering `ok` because it only
  cancelled a queued pulse) stays unused for the 5 s window, so an event it could cause sent from
  elsewhere in those seconds would take its user. Narrow and documented by the rule; acceptable.
- Round 1 nits: `result == "ok"` fixed; `test_commands_through_the_api_end_up_in_the_history` still
  imports `collect` inside the function.

## After QA round 2

- Nit: `collect` imported at the top of `test_devices_commands.py`.
- Observation kept: a command answered `ok` whose target event never comes (a `door/stop` that
  only cancelled queued pulses) stays creditable for its 5 s window; an event it could cause from
  elsewhere in those seconds would take its user. Rare, and bounded by the window.
