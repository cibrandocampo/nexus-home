# T020 — Firmware updates from the platform

**Plan**: docs/plans/platform-middleware.md (phase 3) · **Depends on**: T018, T019

## Context
An admin installs a version on a device. The board downloads the file from the platform over plain HTTP
on the LAN, flashes itself and restarts; the platform follows it to the end, as `tools/update.sh` does.

## Objective
`GET /api/devices/{id}/firmware` answers the device's firmware in the shape of Home Assistant's `update`
entity; `POST /api/devices/{id}/firmware {version}` runs an update and records it.

## Step 1 — Serving the file
`DEVICE_BASE_URL` (e.g. `http://10.1.1.20:8000`, the app's LAN address and published port; empty by
default: an update then answers 409 `device_base_url_missing`, the rest of the app works without it). `GET` and `HEAD /api/firmware/download/{ticket}/<type>-<version>.ota`
with no auth: the ticket is random, created per update and valid until it ends (at most 10 min); 404
otherwise; no redirects; `Content-Length` set.

## Step 2 — Update
- `GET /api/devices/{id}/firmware` (user+): `installed_version` (`sw_version`), `latest_version` (newest
  stable release for the type, or null), `release_summary` (first lines of its notes), `release_url`,
  `in_progress`, `update_available`, and the last update (from, to, result, when, by whom).
- `POST /api/devices/{id}/firmware {version, source?}` (admin): the version must be in the catalogue
  (404 `firmware_not_found`); one update at a time per device (409 `update_in_progress`); offline device
  409 `device_offline`; the board's `door_busy` → 409. Runs as a background task (the poller's
  supervisor style, one per update) and answers 202 with the update record.
- The task: mark the device updating (the poller pauses it: no offline flag, no failed polls), `POST
  /firmware {url}` with a 150 s timeout under the host lock; board errors (`server_unreachable`,
  `file_not_found`, `download_*`, `verify_failed`, `storage_error`) end it as failed with that code; then
  wait up to 3 min for the board to answer again with a fresh uptime and the requested version; a lost
  answer is resolved by asking `/info` which version runs (as `update.sh`). Result `ok`, `failed:<code>`,
  `wrong_version`, `timeout`.
- `FirmwareUpdate` record: device, user, from, to, source, started/finished, result. Bus events
  `UpdateStarted` / `UpdateFinished` (the HA adapter's `in_progress` and result).
- Admin-only; rate limited.

## Step 3 — Tests
Fake board scripted through every path (ok, each board error, lost answer then ok, lost answer and old
version, timeout, wrong version, door busy, offline, concurrent update refused, ticket served once valid
and 404 after), the poller pause, roles, the HA-shaped answer.

## DoD
1. `make lint-backend coverage-backend` pass, coverage ≥ 95 %.
2. Dev stack: an uploaded test version installed on `sim-garage-a` through the API ends `ok` with the
   new version; a second request meanwhile gets 409.

## Files
| File | Action |
|------|--------|
| `platform/backend/app/firmware/{updates,download}.py`, `devices/poller.py`, `devices/bus.py`, router, schemas, models | Create / modify |
| `platform/backend/alembic/versions/<date>_firmware_updates.py` | Create |
| `platform/backend/tests/test_firmware_updates.py` | Create |
| `.env.example`, `docs/configuration.md`, `.claude/skills/platform-api/SKILL.md` | Modify |
