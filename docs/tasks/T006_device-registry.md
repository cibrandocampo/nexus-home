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
