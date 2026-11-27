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

## Implementation notes

- `devices/scan.py`: `addresses()` (IPv4 CIDRs or single addresses, host bits allowed, duplicates
  probed once, more than 1024 addresses → 400 `scan_too_large`, a bad `SCAN_RANGES` → 400
  `invalid_scan_ranges`), `probe_all()` (a semaphore of `SCAN_CONCURRENCY`, `SCAN_TIMEOUT_S` per
  address, anything that is not a nexusHome `/info` is skipped), one scan at a time (409
  `scan_in_progress`), rate limit `SCAN_USER` (30 per hour per admin).
- A registered device found at another address gets the new host only when its stored host is an
  IPv4 address (DHCP); a hostname (`sim-garage-a`, `bench.lan`) already follows the board and is kept.
- API: `POST /api/devices/scan` (`{"ranges": [...]}`, optional: default `SCAN_RANGES`) answers
  `{items, scanned, duration_s}`, unregistered first, then by address; each item carries `registered`
  and the platform `id` when registered. `GET /api/devices/scan-ranges`. Both declared before
  `/{device_pk}` (they would match it otherwise). The answer is bounded (≤ 1024 probes), not paginated.
- `SCAN_CONCURRENCY` default 64 instead of the planned 32: each address gets one probe, so no board
  sees more than one request; a /24 of the LAN takes 8.3 s instead of 13.3 s.
- DoD 2: a scan of the dev /16 is refused (`scan_too_large`); of `172.19.0.0/24` lists both simulators,
  `garage-5e1a0a` as registered with its id, in 13.5 s (with 32 at once).
- DoD 3 (partial): `10.1.3.0/24` from the dev backend finds the production board `garage-3562d4`
  (2.0.5, read-only `GET /info`) in 8.3 s. **NEEDS USER**: the bench board was unplugged (no
  `/dev/ttyACM0`, 10.1.3.114 silent); re-run the scan with it connected to see `garage-33ad84`.
- Codes for the UI: `scan_too_large`, `invalid_scan_ranges`, `scan_in_progress`.
- Evidence: `docs/tasks/evidence/T007/` (`tests.txt`, `scan-dev.txt`, `scan-lan.txt`).

## QA — RETURNED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | `make lint-backend` (ruff check + format) | `docs/tasks/evidence/T007/qa/lint.txt` | PASS |
| 2 | `make coverage-backend`: 416 passed, 100 % (scan.py fully covered) | `docs/tasks/evidence/T007/qa/coverage-backend.txt` | PASS |
| 3 | Full suites: simulator (90 passed), frontend (128 passed), garage firmware host tests | `docs/tasks/evidence/T007/qa/test-simulator.txt`, `test-frontend.txt`, `firmware-host-tests.txt` | PASS |
| 4 | DoD 2: dev scan of `172.19.0.0/24` lists `garage-5e1a0b` (unregistered) and `garage-5e1a0a` (`registered: true`, id 5), in 8.0 s; `/16` → 400 `scan_too_large`; `/33` and IPv6 → 422; a concurrent scan → 409 `scan_in_progress`; no auth → 401; `scan-ranges` → default | `docs/tasks/evidence/T007/qa/scan-dev.txt` | PASS |
| 5 | A registered hostname (`sim-garage-a`) is kept after the scan found it at 172.19.0.6 | `docs/tasks/evidence/T007/qa/hosts-after.txt` | PASS |
| 6 | DoD 3: LAN scan `10.1.3.0/24` finds `garage-3562d4` in < 15 s (7.8–8.7 s) — 5 of 6 runs; the first run missed it (`items: []`) although a direct `GET /info` answered in 0.3 s right after | `docs/tasks/evidence/T007/qa/scan-lan.txt`, `scan-lan-2..6.txt`, `prod-info-get.txt`, `prod-info-cold-latency.txt` | PASS (see O1) |
| 7 | DoD 3: bench board `garage-33ad84` found | — (board unplugged) | NEEDS USER |
| 8 | Review: host move on an ambiguous / spoofed device id | `platform/backend/app/devices/scan.py:98-102` | FAIL (B1) |

### Blockers
- **B1**: `platform/backend/app/devices/scan.py:98-102` (`_follow_moves`) — expected: the host of a
  registered device moves only when the board is really gone from its stored address. Found: the loop
  moves `device.host` to any other address whose `/info` claims the same `id`, even when the board
  still answers at its stored host in the same scan. Example: `garage-3562d4` registered at
  `10.1.3.103` and answering there, plus any LAN host at `10.1.3.200` serving a copy of its `/info`
  → the 103 entry is skipped (same host), the 200 entry moves the device to `10.1.3.200`, and from then
  on the platform sends that board's stored bearer token to the impostor on every authenticated call
  (token exfiltration and loss of control of the door; platform-security: input from devices is
  untrusted). Two boards with a cloned id flip the host on every scan the same way, and the answer
  lists the same `device_id` twice. Expected fix: when an id answers at more than one address, or
  still answers at its stored host, do not move it (and log the conflict by device id); tests for
  both cases (still answering at the stored host + duplicate id elsewhere → host unchanged; the same id
  at two new addresses → host unchanged). No current test covers a duplicated id
  (`tests/test_devices_scan.py` only has distinct ids).

### Observations
- **O1**: one LAN scan of six missed the production board (`scan-lan.txt`), with no error surfaced:
  one probe per address with a 1.5 s timeout means a board that is busy with another client (the
  single-socket firmware, e.g. the light logger) at that instant is silently absent. Not blocking (a
  re-scan finds it; the plan defines one short probe), but worth a note in the UI copy / docs, or a
  single retry of addresses that failed fast (connection refused/reset) rather than timed out.
- **O2**: an admin can point the scan at any IPv4 range (loopback, link-local `169.254.0.0/16`, the
  compose network). Only `GET /api/v1/info` is sent and only a valid nexusHome `/info` is reflected
  back, so the SSRF surface is small; acceptable for an admin-only endpoint.
- **O3**: `configuration.md` says a /24 takes "about 7 s"; measured 7.8–8.7 s on the LAN and 8.0 s on
  the compose network. Cosmetic.

## Fixes after QA round 1

- **B1**: `_follow_moves` groups the scan's answers by device id and moves a registered device's
  host only when its id answered at exactly one new address and the stored host no longer answers
  as that device (one extra `GET /info` to the stored host, which may be outside the scanned
  ranges). Otherwise the host is kept and a warning logged by device id. Both answers stay in the
  results for the admin to see. Tests: a copy of the `/info` elsewhere while the board answers at
  home; the id at two new addresses; the board still answering at home outside the scanned range;
  another board now at the old address (the move still happens). Mutation: without the guard, the
  two tests that depend on it fail.
- O1: documented in `docs/configuration.md` (one probe per address; a busy board can be missed;
  scan again). O3: timings corrected (/24 about 8 s, /23 about 16 s).
- Dev database: merging `main` brought Postgres 19 (Dependabot #7); the dev volume held 18 data, so
  the container refused to start. Data dumped with a temporary `postgres:18-alpine`, restored into
  19; the 18 data directory kept in the volume `nexus-dev_pg18-backup`.
- Suite: 420 passed, coverage 100 %.

## QA — APPROVED (round 2)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | B1 re-check: `_follow_moves` groups by id; no move when the stored host is among the answers, when the id answers at more than one new address, or when the stored host still answers as the board (extra read-only `GET /info`); four new tests | `platform/backend/app/devices/scan.py:99-122`, `platform/backend/tests/test_devices_scan.py:257-297` | PASS |
| 2 | Mutation: guard replaced by `if False:` in a throwaway copy → `test_its_id_at_two_new_addresses` and `test_still_answering_at_home_outside_the_scanned_range` fail | `docs/tasks/evidence/T007/qa/r2/mutation-guard.txt` | PASS |
| 3 | `make lint-backend` | `docs/tasks/evidence/T007/qa/r2/lint.txt` | PASS |
| 4 | `make coverage-backend`: 420 passed, 100 % | `docs/tasks/evidence/T007/qa/r2/coverage-backend.txt` | PASS |
| 5 | Full suites: simulator 90 passed, frontend 128 passed, garage firmware host tests | `docs/tasks/evidence/T007/qa/r2/test-simulator.txt`, `test-frontend.txt`, `firmware-host-tests.txt` | PASS |
| 6 | DoD 2: `172.19.0.0/24` lists `garage-5e1a0b` (unregistered) and `garage-5e1a0a` (`registered: true`, id 5) in 8.5 s; /16 → 400 `scan_too_large`; /33 and IPv6 → 422; concurrent scan → 409 `scan_in_progress`; no auth → 401; `scan-ranges` → default | `docs/tasks/evidence/T007/qa/r2/scan-dev.txt` | PASS |
| 7 | Registered hostname `sim-garage-a` kept after being found at 172.19.0.6 | `docs/tasks/evidence/T007/qa/r2/devices-after.txt` | PASS |
| 8 | DoD 3: `10.1.3.0/24` finds `garage-3562d4` (10.1.3.103) in 8.1 s and 8.0 s, 2 of 2 runs (only `GET /api/v1/info` sent) | `docs/tasks/evidence/T007/qa/r2/scan-lan-1.txt`, `scan-lan-2.txt` | PASS |
| 9 | DoD 3: bench board `garage-33ad84` found | — (board unplugged) | NEEDS USER |
| 10 | Docs: O1 and O3 addressed in `platform/docs/configuration.md`; error codes in `platform-api` skill | `git diff` | PASS |

### Observations
- **O1**: when the stored host is among the answers and the same id also answers at another
  address (the round-1 impostor case), the host is correctly kept but nothing is logged; the
  warning is only emitted on the other branches. A log line there would surface a cloned id.

## After QA round 2

- The round 2 observation: a cloned id is now logged also when the board answers at its stored host
  (`test_a_cloned_id_is_logged_even_when_the_board_answers_at_home`). 421 passed, coverage 100 %.
