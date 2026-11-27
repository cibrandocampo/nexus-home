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
