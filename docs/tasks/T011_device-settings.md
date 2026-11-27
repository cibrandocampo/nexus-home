# T011 — Device settings, restart and token rotation

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T006

## Context
Admins change a board's stored settings (name, times, night level, LED matrix), restart it and
rotate its token from the platform. The WiFi network is not offered (it can cut the board off).

## Objective
Admin endpoints read and write the driver's settings fields, restart the board, rotate and reveal the
token; every change is recorded like a command.

## Step 1 — Settings
- `GET /api/devices/{id}/settings` (`RequireAdmin`): `GET /settings` on the board, filtered to the
  driver's fields (T006 drivers: never `wifi_*`, never `token`). Unknown type → 404
  `settings_not_supported`.
- `PATCH /api/devices/{id}/settings` (`RequireAdmin`): only the driver's fields, validated with the
  board's ranges by the platform first (422 `validation_error`), then `POST /settings` with only the
  changed fields. Board `invalid_*` → 400 with the same code; `save_failed` → 502 `device_save_failed`.
  A changed `name` updates the stored device name. Answers the new settings.
- Text as raw UTF-8, byte limits as the board (a name holds 32 bytes: a 17 × "ñ" name is refused by the
  platform with the board's code `invalid_name`).

## Step 2 — Restart
`POST /api/devices/{id}/restart` (`RequireAdmin`): board `POST /restart`; `door_busy` → 409. The poller
sees the reboot (T008).

## Step 3 — Token
- `POST /api/devices/{id}/rotate-token` (`RequireAdmin`): new random token → `POST /settings {"token"}`
  with the old one → check with `GET /settings` and the new one → store it. If the board took it but
  the check fails, keep both tried tokens out of the logs and answer 502 `device_token_unconfirmed`
  with the device left on the new token stored (the board is the source of truth: retry the check on
  the next poll of `/settings`).
- `GET /api/devices/{id}/token` (`RequireAdmin`): the plain token, so the admin can type it in the
  board's own web page. Rate limited; every reveal recorded (`DeviceCommand` with entity `token`,
  command `reveal`, no token stored there).
- `PATCH /api/devices/{id}` (`RequireAdmin`) `{host?, token?}`: fix a wrong host or re-enter the
  token after a key loss; the token is checked like on add.

## Step 4 — Tests
Each endpoint: roles, success, board errors (`invalid_*`, `save_failed`, `door_busy`, unreachable),
platform-side validation (ranges, byte length with non-ASCII), WiFi fields never forwarded, token
rotation success and unconfirmed path, reveal recorded and rate limited, host/token edit.

## DoD
1. `make lint-backend coverage-backend` pass (coverage ≥ 95 %).
2. Dev stack: `PATCH settings {"light_s": 300}` → the simulator's `GET /settings` shows 300; a name
   "Garaxe ñ" round-trips; `rotate-token` → the simulator accepts only the new token.
3. Bench board: change `light_s` and back, rotate its token (the new token stays in the platform; the
   user can read it with `GET /token`). Never the production board.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-backend test-backend` | `tests.txt` | 0 failures |
| 2 | Simulator | curl as admin | `settings.txt` | values applied, token rotated |
| 3 | Bench board | curl as admin | `bench.txt` | applied and reverted |

## Files
| File | Action |
|------|--------|
| `platform/backend/app/devices/settings.py`, `router.py`, `schemas.py`, `drivers.py` | Create / modify |
| `platform/backend/tests/test_devices_settings.py` | Create |
| `.claude/skills/platform-api/SKILL.md` | Modify (codes) |

## Implementation notes

- `devices/settings.py`; endpoints in `devices/router.py` (all `RequireAdmin`):
  - `GET /api/devices/{id}/settings`: the board's `GET /settings` filtered to the driver's fields
    (never `wifi_*`, never `token`); an unknown type → 404 `settings_not_supported`.
  - `PATCH /api/devices/{id}/settings`: validated with a model built from the driver (`settings_model`:
    ranges of `settings.h`, strict types, the name counted in UTF-8 bytes, plain text, no unknown or
    WiFi or token field) → 422 `validation_error` with the field in `details`. The task asked for the
    board's own `invalid_name`; the platform's validation envelope is used instead, as everywhere else
    in the API, and the board's `invalid_*` codes still pass through with 400 when the board refuses.
    Only the fields that differ from the board's current settings are sent; none → nothing is sent.
    `save_failed` → 502 `device_save_failed`. A new name renames the device.
  - `POST /api/devices/{id}/restart` (204): `door_busy` → 409.
  - `POST /api/devices/{id}/rotate-token` (204): new `token_urlsafe(24)` set with the old token, then
    confirmed with `GET /settings`; whatever token the board accepts afterwards is the one kept (a lost
    answer is resolved by trying the new token, then the old one); neither → 502
    `device_token_unconfirmed`.
  - `GET /api/devices/{id}/token`: `{"token"}` with `Cache-Control: no-store`; 404
    `device_has_no_token`.
  - `PATCH /api/devices/{id}` `{host?, token?}`: a new host must answer `/info` as the same device id
    (409 `device_mismatch`, 422 `not_a_device`, 502 `device_unreachable`); a token is checked like on
    add.
  - Rate limit `DEVICE_TOKEN_USER` (20 per hour per admin) on rotate, reveal and a re-entered token.
  - Every change, restart, rotation and reveal is a `DeviceCommand` (entities `settings`, `device`,
    `token`), never with a token in `params`; marked `used` so it is never credited to history events.
- DoD 2: light time 300 and the name "Garaxe ñ" reach the simulator (its own `/settings` shows them) and
  rename the device; a 17 × "ñ" name → 422; after `rotate-token` the simulator refuses the old token
  (401) and accepts the new one; restart → `reset_reason: software` and the poller logs the restart.
  The simulator's settings and its `.env` token were put back afterwards (`settings.txt`).
- DoD 3: **NEEDS USER** — the bench board is unplugged.
- Suite: 604 passed, coverage 100 %. Once (not reproduced) `users/service.py` 85–87 (the concurrent
  user-creation branch, from the template) was not hit by its concurrency test: a timing-dependent
  test, not part of this task.

## QA — RETURNED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Backend lint and format (`make lint-backend`) | `docs/tasks/evidence/T011/qa/lint.txt` | PASS |
| 2 | Backend suite with coverage (`make coverage-backend`): 604 passed, 100 % | `docs/tasks/evidence/T011/qa/coverage.txt` | PASS |
| 3 | Simulator suite (`make test-simulator`): 90 passed | `docs/tasks/evidence/T011/qa/simulator.txt` | PASS |
| 4 | Frontend suite (`make test-frontend`): 128 passed | `docs/tasks/evidence/T011/qa/frontend.txt` | PASS |
| 5 | Firmware host tests (`make test`, garage) | `docs/tasks/evidence/T011/qa/firmware-tests.txt` | PASS |
| 6 | DoD 2 on the dev stack: roles (user 403, anonymous 401 on all six endpoints), `light_s` 300 and "Garaxe ñ" reach the simulator and rename the device, 16 × ñ accepted, 17 × ñ / WiFi / token / out of range / wrong types / control chars → 422, rotation (old token 401, new 200), reveal `no-store`, `device_mismatch`, re-entered token checked, restart → `software`, audit rows without tokens; simulator and platform put back on the `.env` token | `docs/tasks/evidence/T011/qa/dod2-simulator.txt` | PASS |
| 7 | No token in the backend logs during the run | `docs/tasks/evidence/T011/qa/logs-no-token.txt` | PASS |
| 8 | Rotation: board takes the new token, the confirmation fails (QA probe test, not in the repo) | `docs/tasks/evidence/T011/qa/probe-rotation-lost-token.txt` | FAIL |
| 9 | DoD 3 bench board | — (board unplugged) | NEEDS USER |

### Blockers
- **B1**: `platform/backend/app/devices/settings.py:203-207` (`rotate_token`) — the task (Step 3) requires
  that when the board took the new token but the check fails, the platform answers 502
  `device_token_unconfirmed` **with the new token stored**. Found: the new token is only stored when the
  confirmation `GET /settings` with it succeeds; otherwise the old one stays. When the board answered 200 to
  `POST /settings {"token"}` (or the old token is now refused) and the confirmation is lost (timeout, 503),
  the new token exists only in memory and is discarded: the board ends on a token nobody knows, recoverable
  only physically (setup jumper). The probe (POST answered, both confirmation reads time out) shows 502
  `device_token_unconfirmed`, board on the new token, platform still storing `board-token-1`. Expected: store
  the new token whenever the board accepted the POST, or whenever the old token is no longer accepted, and keep
  the old one only when the board is known to still accept it and not the new one. Add assertions on the stored
  token to `test_rotation_the_board_does_not_confirm` (it currently checks only the status and the audit row),
  plus a case for "no answer to the POST, new and old both refused".

### Observations (non-blocking)
- Step 1 asked for the board's own code `invalid_name` on a 17 × "ñ" name; the platform answers 422
  `validation_error` with `details[].loc = ["body","name"]`. Documented in the implementation notes; confirm
  with the user before T014 relies on it, since it deviates from the written task.
- `PATCH /api/devices/{id}` records a `DeviceCommand` only on success; a refused re-entered token or a
  `device_mismatch` leaves no audit row (settings, restart and rotation record their failures).
- A host change probes an arbitrary admin-given address and is not rate limited (only a re-entered token is);
  admin-only, redirects off, so low risk, but `DEVICE_ADD_USER` applies to the equivalent probe on add.

## Fixes after QA round 1

- **B1**: `rotate_token` now follows the board: after the `POST /settings {"token"}` (answered or
  lost), the new token is tried, then the old one. New accepted → new stored, previous cleared. Old
  still accepted → old kept (502 `device_unreachable`, audit `kept`). Neither → the new token is
  stored **and** the old one kept in `token_previous_encrypted` (new column, migration
  `20261127_a66a900f09fe_device_previous_token`), 502 `device_token_unconfirmed`: the board is never on
  a token the platform does not have. `GET /token` answers `{"token", "previous_token"}`; a confirmed
  rotation or a re-entered token clears the previous one. Tests: the board took it and the check
  fails (stored new, previous old, both revealed); no answer at all; the board says ok but keeps the
  old token; the previous token cleared. Mutation (new token not stored when neither is accepted)
  fails two of them.
- O2: refused `PATCH /api/devices/{id}` attempts are audited (`device_mismatch`, `device_token_invalid`, …).
- O3: a host change is rate limited like an add (`DEVICE_ADD_USER`).
- O1 (`validation_error` instead of the board's `invalid_name`): kept and reported to the user; the UI
  (T014) reads the field from `details`.
- Suite: 609 passed, coverage 100 %.

## QA — RETURNED (round 2)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Backend lint and format (`make lint-backend`) | `docs/tasks/evidence/T011/qa/r2/lint.txt` | PASS |
| 2 | Backend suite with coverage (`make coverage-backend`): 609 passed, 100 % | `docs/tasks/evidence/T011/qa/r2/coverage.txt` | PASS |
| 3 | Simulator suite (`make test-simulator`): 90 passed | `docs/tasks/evidence/T011/qa/r2/simulator.txt` | PASS |
| 4 | Frontend suite (`make test-frontend`): 128 passed | `docs/tasks/evidence/T011/qa/r2/frontend.txt` | PASS |
| 5 | Firmware host tests (`make test`, garage-iot-controller) | `docs/tasks/evidence/T011/qa/r2/firmware-tests.txt` | PASS |
| 6 | Round-1 B1 probe (board takes the new token, the check is lost): 502 `device_token_unconfirmed`, new token stored | `docs/tasks/evidence/T011/qa/r2/probe-rotation-lost-token.txt` | PASS |
| 7 | Dev stack: migration column present; roles on reveal/rotate/PATCH (user 403, anonymous 401); reveal `no-store` with `{token, previous_token}`; rotation (old 401, new 200); a wrong re-entered token refused and audited; audit rows without tokens; simulator and platform put back on the `.env` token | `docs/tasks/evidence/T011/qa/r2/dod2-live.txt` | PASS |
| 8 | No token in the backend logs during the run | `docs/tasks/evidence/T011/qa/r2/logs-no-token.txt` | PASS |
| 9 | Two unconfirmed rotations in a row (QA probe, not in the repo) | `docs/tasks/evidence/T011/qa/r2/probe-double-unconfirmed.txt` | FAIL |
| 10 | DoD 3 bench board | — (board unplugged) | NEEDS USER |

### Blockers
- **B1** (round 1): fixed. Check 6.
- **B2**: `platform/backend/app/devices/settings.py:211-213` (`rotate_token`, "neither accepted" branch) —
  `token_previous_encrypted = token_previous_encrypted or encrypt_token(old)` keeps the *older* previous
  token and throws away `old`, the token the platform was holding. Sequence: rotation 1, the board takes
  new1 and drops off the WiFi → stored new1, previous old0, board on new1 (correct). The admin retries
  while the board is still offline: the POST never arrives, new2 and new1 are both refused (no answer) →
  stored new2, previous old0. The board is on new1, which is no longer stored anywhere: the token is lost,
  recoverable only physically. This is the "board never on a token the platform does not have" promise of
  the fix, broken. Evidence: check 9 (`assert board.token in known` fails; known = {new2, old0}, board =
  new1). Expected: a rotation never discards a token the board might be on. For example, while a previous
  token is pending, settle it first (try the stored one, then the previous one; if neither answers, 502
  `device_unreachable` and send nothing), or refuse to send a new token unless the current one is
  confirmed first. Add a test for two unconfirmed rotations in a row asserting the board's token is
  still stored (current or previous).

### Observations (non-blocking)
- Step 3 says "retry the check on the next poll of `/settings`". Nothing settles a pending previous token
  automatically: the poller reads `/state` and never looks at `token_previous_encrypted`, so after an
  unconfirmed rotation whose POST never arrived, every token-authenticated call (commands, settings) gets
  401 until an admin re-enters the token by hand. The admin can do it (both are revealed), and the fix
  notes say "until a rotation or a re-entered token settles it", but the deviation from Step 3 is not
  stated as one. Either add the settle step (it would also close B2) or record the deviation.
- `test_a_rotation_the_board_still_refuses_keeps_the_old_token`: a board that says ok but keeps the old
  token is answered 502 `device_unreachable`, although it did answer; a clearer code (or the
  `device_error` family) would help the UI in T014. Not a correctness issue.
- O1 from round 1 (`validation_error` instead of the board's `invalid_name`) stays reported to the user.

## Fixes after QA round 2

- **B2**: `service.settle_token` resolves a pending previous token: the stored one accepted → the
  previous one dropped; the previous one accepted → it becomes the stored one; neither → both kept.
  `rotate_token` settles first and, when the board accepts neither, sends nothing (502
  `device_unreachable`, audit `unsettled`), so two unconfirmed rotations in a row can never discard
  the token the board is on (test with the QA's sequence; mutation without the guard fails it).
- Observation 1 (the task's "retry the check on the next poll"): instead of the poller, every
  authenticated use settles a pending token first: commands, reading and changing the settings,
  restart (tests: a command settles on the previous token the board kept; reading settles on the
  current one; a board that accepts neither keeps both).
- Observation 2: a board that answers the token change but keeps its old token → 502
  `device_token_unchanged`; a lost answer with the old token still working stays `device_unreachable`.
- Suite: 613 passed, coverage 100 %.

## QA — APPROVED (round 3)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Backend lint and format (`make lint-backend`) | `docs/tasks/evidence/T011/qa/r3/lint.txt` | PASS |
| 2 | Backend suite with coverage (`make coverage-backend`): 613 passed, 100 % | `docs/tasks/evidence/T011/qa/r3/coverage.txt` | PASS |
| 3 | Simulator suite (`make test-simulator`): 90 passed | `docs/tasks/evidence/T011/qa/r3/simulator.txt` | PASS |
| 4 | Frontend suite (`make test-frontend`): 128 passed | `docs/tasks/evidence/T011/qa/r3/frontend.txt` | PASS |
| 5 | Firmware host tests (`make test`, garage-iot-controller) | `docs/tasks/evidence/T011/qa/r3/firmware-tests.txt` | PASS |
| 6 | QA probes (not in the repo, deleted after the run): round-1 B1 (check lost → board token stored), round-2 B2 (two unconfirmed rotations → second sends nothing, board token still stored; after reconnect a third rotation settles and confirms), and a 1500-step random sequence of rotations (ok, request lost, taken then offline, answer lost, board keeps old, check fails), reconnects, reads, changes, restarts, commands and reveals asserting after every step that the board's token is the stored or the previous one, and that a successful read/change/restart on a reachable board leaves nothing pending | `docs/tasks/evidence/T011/qa/r3/probe-rotation-fuzz.txt` | PASS |
| 7 | Dev stack (DoD 2): roles on all six endpoints (user 403, anonymous 401); settings filtered to the driver; `light_s` 300 and "Garaxe ñ" reach the simulator and rename the device; 17 × ñ / WiFi / token / wrong type / out of range → 422; a pending token settled live on read; rotation (previous none, old 401, new 200); restart → `reset_reason: software` and the poller logs the restart; audit rows without tokens; simulator settings, token and device name put back | `docs/tasks/evidence/T011/qa/r3/dod2-live.txt` | PASS |
| 8 | No token (`.env`, fake, `Bearer`) in the backend logs during the run | `docs/tasks/evidence/T011/qa/r3/logs-no-token.txt` | PASS |
| 9 | DoD 3 bench board | — (board unplugged) | NEEDS USER |

### Blockers
- **B2** (round 2): fixed. Checks 6 and 7; `test_two_unconfirmed_rotations_in_a_row_never_lose_the_board_s_token` covers it.
- None open.

### Observations (non-blocking)
- `models.Device.token_previous_encrypted` comment says the previous token stays "until a rotation or a
  re-entered token settles it"; any authenticated use (command, settings, restart) now settles it too.
- `platform-security` skill's rate-limit row still lists only the auth limits; the device limits
  (`DEVICE_ADD_USER`, `SCAN_USER`, `COMMAND_USER`, now `DEVICE_TOKEN_USER`) are not there (pre-existing gap since T007).
- O1 from round 1 (`validation_error` instead of the board's `invalid_name`) stays reported to the user.

## After QA round 3

- The comment on `Device.token_previous_encrypted` lists everything that settles a pending token.
- `platform-security`: the rate-limit row lists the device limits (add / host change, scan, commands,
  token actions).
