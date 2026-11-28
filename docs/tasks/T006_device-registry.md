# T006 — Device registry, token encryption and the device client

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: none (phase 1 merged)

## Context
Everything in phase 2 needs a stored device and a way to talk to it. This task adds the `devices`
package: the model, the encrypted device token, the HTTP client for a board's `/api/v1`, the type
driver registry, and the admin endpoints to add a device by IP, list, read and remove it.

## Objective
An admin can add a board by IP (with its token, or none for a new board, which then gets one), every
user (`user`+) can list and read devices, an admin can remove one; tokens are encrypted at rest.

## Step 1 — Settings and dependencies
- `requirements.in`: `httpx` (runtime: device client) and `cryptography` (Fernet); `make lock`.
- `Settings.device_token_key`: a Fernet key (url-safe base64, 32 bytes). Dev and tests: a fixed
  development key in `.env.example` / the test env; `production_problems()` refuses an empty key or
  the development one. Rows in `.env.example` and `docs/configuration.md`, with the warning that losing
  the key means re-entering every device token.
- `Settings.device_timeout_s` (default 3.0): per-request timeout to a board.

## Step 2 — Model and migration (`devices/models.py`)
`Device`: `id` (integer pk), `device_id` (string, unique: `/info` `id`, e.g. `garage-3562d4`), `type`
(the id prefix), `name`, `model`, `host` (IP or hostname), `token_encrypted` (nullable), `sw_version`,
`modem_fw`, `mode`, `reset_reason`, `mac`, `entities` (JSONB, from `/info`), `state` (JSONB, nullable),
`rev` (nullable), `online` (bool), `last_seen_at`, `uptime_s`, `created_at`, `updated_at`.
Register in `app/models.py`; `make db-revision m="devices"`, read and fix it, downgrade works.

## Step 3 — Token encryption (`devices/crypto.py`)
`encrypt_token(str) -> str`, `decrypt_token(str) -> str` with Fernet and `device_token_key`. A token
that does not decrypt (key changed) raises a dedicated error the callers map to 409
`device_token_unreadable` ("re-enter the token"). Never log tokens.

## Step 4 — Device client (`devices/client.py`)
Async, httpx, base `http://<host>/api/v1`, timeout `device_timeout_s`, `Connection: close`, no
redirects. A board serves one connection at a time: one `asyncio.Lock` per host serialises every
request to it (polling, commands, settings share it). Methods: `info()`, `state()`, `log()`,
`settings()`, `post(path, json=None)`. Board answers map to `DeviceError(status, code, message)` with
the board's own code (`door_busy`, `unauthorized`, `invalid_*` …); timeouts and connection errors to
`DeviceError(None, "device_unreachable")`; a 2xx that is not the expected JSON to
`device_bad_answer`. Bodies sent as raw UTF-8 JSON (`ensure_ascii=False`: the board refuses
`\u` escapes above 0x7F; see `platform/simulator/README.md`).

## Step 5 — Type drivers (`devices/drivers.py`)
A registry keyed by type with one entry, `garage`: display name, the settings fields it edits (name,
`open_s`, `close_s`, `light_s`, `night_level`, `display` with the board's ranges), the firmware asset
prefix (`garage-`) for phase 3. Unknown types are stored and shown generically (no settings form).

## Step 6 — API (`devices/router.py`, `schemas.py`, `service.py`)
- `GET /api/devices` (`RequireUser`): paginated list (`items/total/page/size`), filter `q` (name or
  device id), ordered by name.
- `GET /api/devices/{id}` (`RequireUser`): detail with entities and last state. Never the token; a
  boolean `has_token`.
- `POST /api/devices` (`RequireAdmin`) `{host, token?}`: reads `/info` (`device_unreachable` 502 if it
  does not answer, `not_a_device` 422 if it is not a `/api/v1` board), refuses a registered `device_id`
  (409 `device_exists`). With a token: checks it with `GET /settings` (401 from the board → 400
  `device_token_invalid`). Without one and `/info` `auth: false`: generates a token
  (`secrets.token_urlsafe(24)`, within the board's 64-byte limit), sets it with `POST /settings
  {"token": …}`, then checks it. Without one and `auth: true` → 400 `device_token_required`. 201 with
  the device.
- `DELETE /api/devices/{id}` (`RequireAdmin`): 204. Unknown id → 404 `device_not_found`.
- Rate limit on `POST /api/devices` (it checks a secret against a board).

## Step 7 — Tests (real Postgres; the board through `httpx.MockTransport` or a simulator
instance)
Every endpoint: anonymous 401, role `none` 403, `user` 403 where admin-only, happy path; every error
code above; token stored encrypted (column ≠ plain token, decrypts back); a new board gets a token
set on it; the client serialises two concurrent requests to the same host; `\u` never sent; timeout →
`device_unreachable`. Error codes get their translations later with the UI (T012–T014) — list them in
the task notes. Coverage stays ≥ 95 % (today 100 %).

## Step 8 — Docs
`platform-architecture` (module table: `devices/`), `platform-api` (error table: new codes),
`docs/configuration.md`.

## DoD
1. `make lint-backend coverage-backend` (from `platform/`) pass (coverage ≥ 95 %).
2. The migration downgrades and upgrades: the backend test session runs downgrade-to-base and upgrade-to-head.
3. Against the dev stack: `curl` with an admin token `POST /api/devices {"host":"sim-garage-a","token":…}`
   → 201; `GET /api/devices` lists it; the row's `token_encrypted` is not the token (psql).
4. A tokenless simulator (`SIM_TOKEN` empty) added without a token ends with a token on the board
   (`GET /settings` on the simulator with the stored token answers 200).
5. With `ENV=production` and the development key, the app refuses to start.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Lint + tests | `make lint-backend test-backend` | `tests.txt` | 0 failures, ≥ 95 % |
| 2 | Add/list | curl against the dev stack | `api.txt` | 201, listed, `has_token` true |
| 3 | Encrypted | psql `select token_encrypted` | `db.txt` | not the plain token |
| 4 | New board | tokenless simulator | `new-board.txt` | board accepts the stored token |
| 5 | Production key | `ENV=production` start | `prod.txt` | refuses with the key problem |

## Files
| File | Action |
|------|--------|
| `platform/backend/app/devices/{__init__,models,schemas,router,service,client,crypto,drivers}.py` | Create |
| `platform/backend/app/models.py`, `main.py`, `core/config.py` | Modify |
| `platform/backend/alembic/versions/<date>_devices.py` | Create |
| `platform/backend/requirements.in`, `requirements.txt` | Modify |
| `platform/backend/tests/test_devices_*.py` | Create |
| `platform/.env.example`, `platform/docs/configuration.md` | Modify |
| `.claude/skills/platform-architecture/SKILL.md`, `platform-api/SKILL.md` | Modify |

## Implementation notes

- `devices/` package: `models.Device`, `crypto` (Fernet), `client` (`DeviceClient`, `DeviceError`,
  per-host `asyncio.Lock`, module-level `transport` that tests replace), `drivers` (`garage` with the
  `settings.h` ranges), `schemas`, `service`, `router`. Migration `20261127_0eb4bae839e3_devices`.
- `DEVICE_TOKEN_KEY` defaults to a public development key (in `.env.example` too); production refuses
  it and any malformed key (`production_problems`, preflight message). The e2e stack has its own key.
- Runtime dependencies: `httpx` (moved from the dev requirements), `cryptography`.
- Error mapping (`service.device_error`): board unreachable → 502 `device_unreachable`; board 401 →
  409 `device_token_invalid` (stored token), but 400 `device_token_invalid` while adding (the admin
  typed it); other board errors → 502 `device_error`. Add: 422 `not_a_device`, 409 `device_exists`
  (also on the insert race), 400 `device_token_required`.
- A board without a token (`/info` `auth: false`) gets `secrets.token_urlsafe(24)` (32 characters)
  through `POST /settings`, then the token is checked with `GET /settings`.
- Rate limit `DEVICE_ADD_USER` (20 per hour per admin).
- Tests: `tests/fakeboard.py` (a scriptable board over `httpx.MockTransport`, autouse `lan`
  fixture: no test reaches the network), `test_devices_registry.py`, `test_devices_client.py`,
  `test_devices_drivers.py`, production key tests. 392 tests, coverage 100 %.
- Codes the UI must translate (T012–T014): `device_not_found`, `device_exists`, `not_a_device`,
  `device_unreachable`, `device_error`, `device_token_invalid`, `device_token_required`,
  `device_token_unreadable`.
- Evidence: `docs/tasks/evidence/T006/` (`tests.txt`, `api.txt`, `db.txt`, `new-board.txt`,
  `prod.txt`).

## QA — RETURNED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Backend lint + format (`make lint-backend`) | `docs/tasks/evidence/T006/qa/lint.txt` | PASS |
| 2 | Backend tests + coverage (`make coverage-backend`): 392 passed, 100 % | `docs/tasks/evidence/T006/qa/coverage.txt` | PASS |
| 3 | Device + production tests, 3 consecutive runs (104 passed each) | `docs/tasks/evidence/T006/qa/targeted-3x.txt` | PASS |
| 4 | Migration downgrade-to-base / upgrade-to-head in the test session (`conftest.py:33-34`, suite green) | `docs/tasks/evidence/T006/qa/coverage.txt` | PASS |
| 5 | Other suites: frontend tests + lint, simulator lint + tests, e2e lint | `docs/tasks/evidence/T006/qa/other-suites.txt` | PASS |
| 6 | Firmware host tests (garage) | `docs/tasks/evidence/T006/qa/firmware-tests.txt` | PASS |
| 7 | Production image builds with the new runtime dependencies | `docs/tasks/evidence/T006/qa/image-build.txt` | PASS |
| 8 | DoD 5: production image refuses the default key, the `.env.example` key and a malformed key; starts preflight with a fresh key | `docs/tasks/evidence/T006/qa/prod.txt` | PASS |
| 9 | DoD 3: add sim-garage-a with its token → 201 `has_token` true, listed, detail without token; every error code against the dev stack (409, 400×2, 502, 422 `not_a_device` on Mailpit, 404, 401) | `docs/tasks/evidence/T006/qa/api.txt` | PASS |
| 10 | DoD 3: `token_encrypted` is Fernet ciphertext, ≠ and not containing the plain token, decrypts back | `docs/tasks/evidence/T006/qa/db.txt` | PASS |
| 11 | DoD 4: tokenless simulator added without a token → 201; board now `auth: true`, 401 without token, 200 with the stored (decrypted) token | `docs/tasks/evidence/T006/qa/new-board.txt` | PASS |
| 12 | DELETE happy path against the dev stack (204, then 404) | `docs/tasks/evidence/T006/qa/delete.txt` | PASS |
| 13 | Review: tests have specific assertions for the concept they name | `platform/backend/tests/test_devices_client.py:63-71` | FAIL |

### Blockers
- **B1**: `platform/backend/tests/test_devices_client.py:63-71` — `test_different_boards_are_not_serialised`
  asserts only `a.requests and b.requests`; the comment claims both ran in the same window, but nothing
  checks it. The test passes unchanged with one global lock instead of one per host (requests to
  different boards serialised), so the per-host part of the lock design is untested (test-discipline:
  no vague asserts, one concept with a specific assertion). Expected: an assertion that the two
  requests overlapped, e.g. a shared in-flight counter on `Lan` with `max_in_flight == 2`, or each
  board recording that the other was in flight while it slept.

### Observations (non-blocking)
- `service._give_token` sets the token on the board before the insert: if the insert then loses the
  race (`device_exists`) or the token check after `POST /settings` fails, the board keeps a token
  nobody stored. Rare (admin-only, board just registered by the other request); worth a note for T011
  (token rotation) or the UI copy.
- `DeviceClient` builds `httpx.AsyncClient` with the default `trust_env=True`: an `HTTP_PROXY` in the
  container environment would route board traffic through the proxy. `trust_env=False` would pin LAN
  traffic to direct connections.
- The timeout test simulates `httpx.ConnectTimeout`; a read timeout is covered by the same
  `httpx.HTTPError` branch, but no test exercises a real `ReadTimeout`.
- `service.add_device` is ~33 lines (architecture checklist: split over 30).
- Hostnames are accepted (`host` pattern), so an admin can make the backend probe any name it
  resolves (`db:5432`, `mailpit:8025` → `not_a_device`). Admin-only and needed for the simulators;
  acceptable, noted for the security review.
- QA left the dev stack with sim-garage-a registered (re-added as id 3), as it found it.

## Fixes after QA round 1

- **B1**: `Lan` counts requests in flight across every board; `test_different_boards_are_not_serialised`
  asserts `lan.max_in_flight == 2`. Mutation check: with one global lock in `host_lock` the test fails
  (1 failed, 19 passed), with the per-host locks it passes.
- O2: the device client uses `trust_env=False` (no proxy from the environment); tested by spying on the
  `httpx.AsyncClient` arguments with `HTTP_PROXY` set.
- O3: read-timeout test (`httpx.ReadTimeout` mid-request → `device_unreachable`).
- O4: `add_device` split into `_read_info`, `_token_for` and the insert.
- O1: `add_device` holds a lock per board id (`register:<id>`) from the existence check to the
  insert, so two admins adding the same tokenless board at once cannot give it two tokens: the second
  waits and gets 409 `device_exists` without touching the board. Tested with two concurrent adds.
- O5 (any hostname accepted) is kept: admin-only, and the simulators are reached by name.
- Suite: 395 passed, coverage 100 %; client tests 3 runs in a row green. Mutation: without the
  registration lock the concurrent-add test fails.

## QA — APPROVED (round 2)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Round 1 B1: `test_different_boards_are_not_serialised` asserts `lan.max_in_flight == 2`; QA mutation (one global lock patched into `client.host_lock` via a pytest plugin, repo untouched) makes it fail | `docs/tasks/evidence/T006/qa/r2/mutation.txt` | PASS |
| 2 | Registration lock: QA mutation (fresh lock per call in `service.host_lock`) makes `test_two_adds_of_the_same_new_board_give_it_one_token` fail | `docs/tasks/evidence/T006/qa/r2/mutation.txt` | PASS |
| 3 | Device + production tests, 3 consecutive unmutated runs (107 passed each) | `docs/tasks/evidence/T006/qa/r2/mutation.txt` | PASS |
| 4 | Backend lint + format (`make lint-backend`) | `docs/tasks/evidence/T006/qa/r2/lint.txt` | PASS |
| 5 | Backend tests + coverage (`make coverage-backend`): 395 passed, 100 %; migration downgrade/upgrade in the session | `docs/tasks/evidence/T006/qa/r2/coverage.txt` | PASS |
| 6 | Other suites: frontend tests (128) + lint, simulator tests (90, 99 %) + lint, e2e lint | `docs/tasks/evidence/T006/qa/r2/other-suites.txt` | PASS |
| 7 | Firmware host tests (garage) | `docs/tasks/evidence/T006/qa/r2/firmware-tests.txt` | PASS |
| 8 | Production image builds | `docs/tasks/evidence/T006/qa/r2/image-build.txt` | PASS |
| 9 | DoD 3: add sim-garage-a with token → 201 `has_token` true, listed, detail without token; 409/400/400/502/422/404/404/401 against the dev stack | `docs/tasks/evidence/T006/qa/r2/api.txt` | PASS |
| 10 | DoD 3: `token_encrypted` is Fernet (`gAAAAA…`), ≠ and not containing the token, decrypts back | `docs/tasks/evidence/T006/qa/r2/db.txt` | PASS |
| 11 | DoD 4: tokenless simulator added without a token → 201; board `auth: true`, 401 without token, 200 with the stored 32-char token | `docs/tasks/evidence/T006/qa/r2/new-board.txt` | PASS |
| 12 | DELETE happy path (204, then 404); throwaway simulator removed | `docs/tasks/evidence/T006/qa/r2/delete.txt` | PASS |
| 13 | DoD 5: production image refuses the default key, the `.env.example` key and a malformed key; a fresh key passes preflight | `docs/tasks/evidence/T006/qa/r2/prod.txt` | PASS |
| 14 | Review of the round-1 fixes (`trust_env=False`, read-timeout test, `add_device` split, registration lock) | `platform/backend/app/devices/{client,service}.py`, `tests/test_devices_client.py` | PASS |

### Observations (non-blocking)
- The registration lock reuses the per-host lock table with the key `register:<device_id>`; it cannot
  collide with a real host because the `host` pattern only allows digits after `:`. Entries stay in
  `_locks` for the life of the process (one per device id ever added): negligible.
- The registration lock is per process; with more than one backend worker the unique constraint
  still returns 409, but the board could get two tokens. Fine for the single-instance deployment;
  worth remembering if the backend ever scales out.
- The dev stack is left with sim-garage-a registered (now id 5), as QA found it.
