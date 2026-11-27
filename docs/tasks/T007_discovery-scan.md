# T007 — Discovery scan

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T006

## Context
Admins should not have to know a board's IP. A scan of the configured ranges finds the boards on
the LAN that are not registered yet, and notices a registered board whose IP changed (DHCP).

## Objective
`POST /api/devices/scan` probes the ranges and answers the devices found, and updates the host of
registered ones found at a new address.

## Step 1 — Settings
`SCAN_RANGES` (comma-separated CIDRs, default `10.1.2.0/23`), `SCAN_CONCURRENCY` (default 32),
`SCAN_TIMEOUT_S` (default 1.5). A range over 1024 addresses is refused (`scan_too_large`, 400) so a
typo cannot scan a /8. `.env.example`, `docs/configuration.md`.

## Step 2 — Scan (`devices/scan.py`)
For every host address of the ranges: `GET http://<ip>/api/v1/info` with `SCAN_TIMEOUT_S`, at most
`SCAN_CONCURRENCY` at once (a semaphore; boards are slow WiFi modules). An answer is a device when it
has `id`, `api: "v1"` and `entities`. Results: `{device_id, name, model, sw_version, host, auth,
registered}`. A registered device found at a different host: its `host` is updated (and logged by
device id). Returns found devices, unregistered first.

## Step 3 — API
`POST /api/devices/scan` (`RequireAdmin`) with optional `{"ranges": ["10.1.3.0/24"]}` (the UI lets the
admin edit them before scanning; default from settings). Validation: valid CIDRs, IPv4, size limit.
One scan at a time (an in-process lock; a second request → 409 `scan_in_progress`). Rate limit.
`GET /api/devices/scan-ranges` (`RequireAdmin`): the configured default, for the form.

## Step 4 — Tests
With a fake transport mapping IPs to answers: finds devices, skips non-devices, timeouts, updates a
moved host, concurrency limit respected (max in flight ≤ setting), size limit, bad CIDR 422, roles,
`scan_in_progress`.

## DoD
1. `make lint-backend coverage-backend` pass (coverage ≥ 95 %).
2. In the dev stack (simulators on the compose network): a scan of the compose network's subnet lists
   `garage-5e1a0a` and `garage-5e1a0b`; after adding one, the scan shows it `registered: true`.
3. On the LAN (from the dev backend container, read-only `GET /info` only): a scan of `10.1.3.0/24`
   finds the bench board `garage-33ad84` and the production board `garage-3562d4`, and takes < 15 s.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-backend test-backend` | `tests.txt` | 0 failures |
| 2 | Dev scan | curl `POST /api/devices/scan` | `scan-dev.txt` | both simulators |
| 3 | LAN scan | curl with `ranges: ["10.1.3.0/24"]` | `scan-lan.txt` | both boards, < 15 s |

## Files
| File | Action |
|------|--------|
| `platform/backend/app/devices/scan.py`, `router.py`, `schemas.py` | Create / modify |
| `platform/backend/app/core/config.py`, `core/ratelimit.py` | Modify |
| `platform/backend/tests/test_devices_scan.py` | Create |
| `platform/.env.example`, `platform/docs/configuration.md` | Modify |
