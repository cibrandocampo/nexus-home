# T005 — Garage device simulator

**Plan**: docs/plans/platform-middleware.md (phase 1) · **Depends on**: T001

## Context
Phase 2 (registry, scan, polling, history, commands, settings) needs a device to talk to in tests,
in the dev stack and in E2E. The real boards are one bench board and one production door. A
simulator that speaks the garage's `/api/v1` exactly as documented in
`devices/garage-iot-controller/README.md` ("API" section) lets all of that run in Docker, and a
contract test keeps it honest when the firmware's API changes.

## Objective
`platform/simulator/` is a small HTTP service that behaves like a garage board for everything phase
2 uses, runs as any number of instances in the dev and E2E stacks, and fails its contract test if its
answers drift from the README.

## Step 1 — Service
Python (FastAPI + uvicorn, hash-pinned like the backend), own `Dockerfile`, no database:
- `GET /api/v1/info` (id `garage-<6 hex>` from `SIM_ID`, name, model, `sw_version`, `modem_fw`, mode,
  `reset_reason`, MAC, entities as the real board lists them), `/state`, `/log` (64 entries, newest
  first, `t` in uptime seconds).
- Door: `open`, `close`, `stop`, `toggle` with the README semantics (no-op cases, `stopped` up/down,
  `door_busy` 409 on an opposite movement or a pulse < 1.2 s after the last), travel times from the
  settings, accelerated by `SIM_SPEED` (default 1). Light: `on` (`duration` query or body, default
  120, 0 = no timer, `invalid_duration`), `off`, `toggle`, auto light on door movement.
- `GET`/`POST /settings` (validation and error codes per README; `token` changes the token; WiFi
  fields accepted and ignored with `testing_wifi` semantics documented as not simulated), `POST
  /restart` (409 while moving; uptime resets, `boot` event, log cleared, `rev` restarts).
- Auth: `Authorization: Bearer <SIM_TOKEN>` on every POST and `GET /settings`; `Origin` ≠ `Host` → 403;
  unknown path 404, wrong method 405, all with the README error envelope.
- `rev` increases on every change; `light_level` drifts without changing `rev`.
- `POST /firmware` answers 501 `not_simulated` for now (phase 3 extends it).
- Test hooks under `/sim/*` (not on real boards, documented as such): set the closed sensor, press
  the button, force `close_failed`, go silent (to simulate offline), so phase 2 tests can drive it.

## Step 2 — Contract test
Tests (pytest, in the simulator's container) parse every JSON example of the README's API section
and check the simulator's answer for the same situation has the same keys, nesting and value types,
and that every error code in the README's error table is produced by some request.

## Step 3 — Stacks
- `platform/dev/docker-compose.yml`: two simulators (`sim-garage-a`, `sim-garage-b`, different ids and
  tokens from `.env.example`), reachable from the backend by service name.
- `platform/e2e/docker-compose.yml`: one simulator (used from phase 2).
- `platform/Makefile`: `test-simulator`, `lint-simulator`, included in `qa`; `platform.yml` CI runs them.

## DoD
1. `make test-simulator` passes, with ≥ 95 % coverage of `simulator/`.
2. The contract test fails when a README example key is renamed (shown by a temporary edit, reverted).
3. A scripted session against `sim-garage-a` in the dev stack: info, open (state `opening`, then `open`
   after the travel time at `SIM_SPEED=10`), stop while moving, `door_busy`, light on with duration,
   settings change, restart — each answer matches the README.
4. `make lint` covers the simulator (ruff) and passes; the platform CI job runs it.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make test-simulator` | `tests.txt` | pass, ≥ 95 % |
| 2 | Contract catches drift | temporary README edit, test, revert | `contract.txt` | fails then passes |
| 3 | Session | curl script against the dev stack | `session.txt` | as stated |
| 4 | Lint and CI | `make lint`; `gh pr checks` | `lint.txt` | pass |

## Files
| File | Action |
|------|--------|
| `platform/simulator/**` | CREATE |
| `platform/dev/docker-compose.yml`, `platform/e2e/docker-compose.yml`, `platform/.env.example`, `platform/Makefile` | MODIFY |
| `.github/workflows/platform.yml` | MODIFY |

## Implementation notes
- Built on Starlette + uvicorn rather than FastAPI: a single dispatcher that routes like `http.cpp`
  (`handle()`), so paths, methods, the order of checks (method → origin → token) and the error
  envelope match the firmware, including its 404/405 answers, which a router would shape differently.
- `sim/garage.py` is a port of `garage.cpp` (`tick()` at 100 Hz, run for the simulated time on each
  request and every 50 ms); `sim/device.py` ports `http.cpp` / `settings.cpp` (identity, entities,
  settings validation with the firmware's codes, token, restart). A physical `Opener` model stands in
  for the single-button opener and the closed sensor; hooks under `/sim/` drive it (README).
- Faithful quirks the tests pin: night is held back for the first 10 s after boot (lamp settle time from
  `lightOffAt = 0`); `/door/stop` during a three-pulse reversal cancels the pending pulses but answers
  409 because the last pulse was under 1.2 s ago.
- Contract (`tests/test_contract.py`): the README's JSON examples (state, log, command answer, error),
  event, source and reason names, and its error table; plus the keys `http.cpp` writes for `/info`,
  `/state` and `/settings`, and the `/info` entity list. Exempt, with reasons in the test: `too_long`
  (the firmware's JSON reader answers the field's own `invalid_*` first, so the API never returns it)
  and the firmware-update 502 codes (phase 3). The Platform workflow now also runs on changes to the
  garage README and `http.cpp`.
- One dependency set (`requirements.in`, hash-pinned; dev-only tool): Starlette 1.10 deprecates `httpx`
  in its test client, so the tests use `httpx2`.
- Stacks: two simulators in the dev compose (tokens and speed in `.env.example`, documented in
  `docs/configuration.md`), one in the e2e compose (`SIM_SPEED=10`, unused until phase 2).
- Evidence: `tests.txt` 77 passed, 98 % coverage; `contract.txt` (a renamed README key in a scratch copy:
  2 failed; the real README: 11 passed); `session.txt` (scripted curl session at `SIM_SPEED=10` from the
  dev network: open → open after 22 s, close, stop part way (`stopped: down`), `door_busy`, light 600 s,
  settings change, 401, restart → `reset_reason: software`, settings kept).
