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

## QA — RETURNED (round 1)

**Date**: 2026-11-26

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | `make test-simulator` command (as the Makefile runs it), 3 runs: 77 passed each, 98 % total (≥ 95 %) | `docs/tasks/evidence/T005/qa/tests.txt` | PASS (but see B1) |
| 2 | Contract catches drift (scratch copies mounted as `/contract`): README State key renamed → 2 failed; `http.cpp` `since_s` renamed → 1 failed; new README error row → 1 failed; new `/info` entity in `http.cpp` → 1 failed; real files → 11 passed | `docs/tasks/evidence/T005/qa/contract.txt` | PASS |
| 3 | Scripted session against `sim-garage-a` (dev stack, `SIM_SPEED=10`, curl container on `nexus-dev_default`): info, opening → open (`travel_end`), restart while moving 409, noop, close, stop → `stopped: down`, `door_busy` (gap and queued reversal), three-pulse close → closed, light 600 s / body 30 s / `invalid_duration`, 401, 403, 405, 404, settings change + `invalid_open_time`, 501, log, restart → `software`, log cleared, `rev` 0, settings kept | `docs/tasks/evidence/T005/qa/session.txt` | PASS |
| 4 | Lint: ruff check + format check pass; `make lint` includes `lint-simulator` and `make test` includes `test-simulator` (`make -n` in `nexus-garage-toolchain`); CI `Simulator` job green, all PR #6 checks pass | `docs/tasks/evidence/T005/qa/lint.txt`, `docs/tasks/evidence/T005/qa/make-n.txt` | PASS |
| 5 | Full suites: backend lint + 325 tests (99 %), frontend lint + 128 tests, e2e Prettier, firmware host tests | `docs/tasks/evidence/T005/qa/full-platform.txt`, `docs/tasks/evidence/T005/qa/firmware-tests.txt` | PASS |
| 6 | Fidelity against the firmware sources (`garage.cpp`, `http.cpp`, `settings.cpp`, `json.h`, `net.cpp`) | `docs/tasks/evidence/T005/qa/fidelity-probes.txt`, `docs/tasks/evidence/T005/qa/reversal-probe.txt` | FAIL (B2, B3) |
| 7 | Compose services, `.env.example`, CI job and path filters, Dependabot, docs (simulator README, dev-workflow, platform-ci, configuration.md) | code review | PASS (observations O4, O6, O7) |

### Blockers
- **B1**: `platform/simulator/sim/garage.py:366`, `:371`, `:352`, `:226`, `:204` — new lines without a test
  (`tests.txt`, coverage "Missing"). Two are README behaviours a platform client depends on: `/door/open` while
  the door is closing → 409 `door_busy` (`:366`, garage.cpp:397) and `/door/open` on a door stopped going down
  → one pulse, `ok` (`:371`, garage.cpp:400). Also untested: auto light leaving a manually held light alone
  (`:226`, garage.cpp:116) and `_reverse_then` refused by the pulse gap (`:352`, garage.cpp:386). `:204`
  (`set_door` to the same state) needs a test or a note that it is unreachable, as in the firmware.
- **B2**: `platform/simulator/sim/device.py:84-90` (`text()`) — string settings are checked on the decoded
  Python string by character count, rejecting any control character. The firmware's reader
  (`devices/garage-iot-controller/firmware/json.h:280-320`) counts bytes (raw UTF-8 passes, `len + 1 >= n`),
  rejects `\u` escapes above 0x7F (json.h:305) and accepts escaped control characters. Probes P1–P4:
  `{"name":"Jardín"}` → simulator 200 `ok`, board 400 `invalid_name`; 20 × "ñ" (40 bytes > 32) →
  simulator 200, board 400 `invalid_name`; `"a\nb"` / `"a\u0001b"` escaped → simulator 400, board 200. A
  platform rename with an accent (a Python JSON encoder escapes non-ASCII by default) passes against the
  simulator and fails on the real board, which is the failure the simulator exists to catch. Expected: field
  reading equivalent to json.h `str` (bytes, escape rules), with tests. Reading `num`/`flag`/`duration` from the
  raw body the same way would also align P5 (non-JSON body: board 200 `ok`, it never answers `invalid_json`;
  simulator 400 `invalid_json`, app.py:115-116) and P6 (`{"duration": 30.5}`: board 30 s via `strtoul`,
  simulator 400), which are not blocking on their own.
- **B3**: `platform/simulator/sim/garage.py:177-182` — `configure()` does not re-decide night as
  `garage.cpp:340-351` does (`decideNight(true)` on every settings save, which drops the hysteresis). Probe P15:
  night with level 690 and `night_level` 700, then `night_level` 695 → board: raw night false at once, `day`
  60 s later; simulator: stays night indefinitely (still `night: true` 70 s later). A platform test that changes
  the night level and expects the board's answer gets a different one.

### Observations (non-blocking)
- **O1** `device.py:147-150` — the MAC is a hash of the id; on the board the id is derived from the MAC
  (`net.cpp:55-56`: `garage-` + last three bytes, lowercase), so `/info` id and MAC never agree here
  (P11, `garage-abc123` / `02:40:C4:0B:0F:AF`). Deriving the last three bytes from `SIM_ID` keeps the invariant.
- **O2** `device.py:306-311` — the `testing_wifi` answer shows the new `wifi_ssid` and `wifi_trying: false`; the
  board answers with the old network (not saved yet) and `wifi_trying: true` (`http.cpp:350-354`, `:252`) (P12).
  The README only says the network "connects at once"; either match the answer or say so.
- **O3** `garage.py:175` — `wifi_up` at boot is recorded without `rev += 1`; on the board it is a `note()`
  (`net.cpp:72`, `garage.cpp:377-381`), so `rev` after a boot is 0 here and ≥ 1 there (P13).
- **O4** Transport limits are neither simulated nor listed under "Not simulated": 1 KB request limit → 413
  `too_large` (`http.cpp:496-506`, P9: a 2 KB request answers 200 here), one connection at a time with
  `Connection: close` (`http.cpp:65`, `:476-485`), 1.5 s request timeout (`:17`, `:508`).
- **O5** `app.py:178` — methods outside GET/POST/PUT/PATCH/DELETE (OPTIONS) get Starlette's plain-text 405, not
  the JSON envelope the board sends for any method (P7). Error answers also lack `Cache-Control: no-store`
  (`app.py:27-28` vs `http.cpp:65`).
- **O6** Contract test reads error codes only from the README: renaming `unauthorized` in `http.cpp` alone still
  passes (contract.txt `cpp_errcode`: 11 passed). Status per code and messages are not compared with
  `respondError` calls, and `garage.cpp`/`settings.cpp`/`json.h` (the logic the simulator ports) are neither
  under contract nor in the workflow path filter, so a behaviour change there does not re-run the simulator
  job. Worth extracting `(status, code)` pairs from `http.cpp`, and a note in the simulator README that
  behaviour drift is guarded by review only.
- **O7** `platform/simulator/Dockerfile:2` — "the dev stack also bind-mounts it" is not true: the dev compose
  services have no volume; only the `make *-simulator` runs mount `simulator/`.
- **O8** `app.py:147`, `:152`, `:154` — hooks with a malformed body (`{"position": "x"}`) raise and answer 500
  instead of 400. Test-only surface.
- **O9** Faithful, worth knowing for phase 2 tests: after `/sim/power_cycle` with the door part way the opener
  keeps its last direction while the board forgets `stopped`, so a `close` can drive the door up and end in
  `close_failed` (seen on the first session attempt on the dev instance, which had been left part way, with
  `name` "Sim A" and `open_s` 12; restored to `open_s` 12 after the session).

## Fixes after QA round 1
- B1: tests for `/door/open` while closing (409) and after a stopped close (one pulse), a reversal
  refused inside the pulse gap, the auto light leaving a hand-held light alone, and `setDoor` to the
  same state (a guard ported from `garage.cpp` that no path reaches today, now commented as such).
  Line coverage 100 %, branch 99 %.
- B2: request bodies are read with a byte-for-byte port of `json.h` (`sim/fwjson.py`): lengths in
  bytes, `\u` above 0x7F refused, escaped control characters accepted, raw ones refused, `30.0`
  refused in settings, `duration` read up to its first non-digit (`30.5` → 30 s, as `findDuration`),
  a non-JSON body changes nothing (200, never `invalid_json`). Tests pin each case.
- B3: `configure()` re-decides night at once (`decideNight(true)`), so raising the night level above
  the reading ends night and logs `day` after the debounce.
- Observations fixed: O1 the MAC ends with the id (`02:00:00:xx:yy:zz`; a malformed `SIM_ID` is refused);
  O2 `testing_wifi` answers with the old network and `wifi_trying: true`, the board goes silent for
  `SIM_RESTART_S` and comes back with `wifi_up` and `wifi_changed`; O3 the boot `wifi_up` increments
  `rev`; O4 the transport limits and the always-working WiFi change are listed under "Not simulated";
  O5 errors carry `Cache-Control: no-store`, OPTIONS gets the JSON 405; O6 the contract also checks each
  documented error's status against the simulator and against every literal `respondError` in
  `http.cpp`, and the Platform workflow runs on changes to `garage.cpp`/`.h`, `settings.cpp`, `json.h`
  and `config.h` too; O7 Dockerfile comment; O8 malformed hook bodies answer 400 `invalid_hook_body`;
  O9 the power-cycle difference is described in the simulator README.
- Evidence: `tests-r2.txt` (lint clean; 90 passed, contract included).

## QA — APPROVED (round 2)

**Date**: 2026-11-26 · reviewed `f908829` + `474204d`

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Lint (ruff check + format) and the simulator tests as `make test-simulator` runs them, 3 runs: 90 passed each, lines 100 %, total 99 % (branch partials only: device.py 120->122, garage.py 283->exit, 369->374) | `docs/tasks/evidence/T005/qa/tests-r2.txt` | PASS |
| 2 | B1: tests added for `/door/open` while closing (409), open after a stopped close (one pulse), reversal refused in the gap, auto light leaving a hand-held light, `set_door` to the same state (commented as unreachable, as in the firmware) | `docs/tasks/evidence/T005/qa/tests-r2.txt` (no missing lines) | PASS |
| 3 | B2: `sim/fwjson.py` compared line by line with `json.h` (`find`, `str`, `flag`, `num`) and `http.cpp` `findDuration`; round-1 probes re-run: Jardín raw 200 / escaped 400 `invalid_name`, 20 × ñ 400, 16 × ñ 200, escaped `\n` and `\u0001` 200, raw 0x01 400, non-JSON body 200 `ok`, body `duration` 30.5 → 30 s, query `600abc` → 600 s, overflow → 400, query without `duration` falls back to the body, `30.0` and `1e3` → `invalid_open_time` | `docs/tasks/evidence/T005/qa/fidelity-probes-r2.txt` | PASS |
| 4 | B3: `configure()` re-decides night with `fresh=True`; P15 now: night_level 700 → 695 at level 690 → raw night false at once, `day` logged after the debounce | `docs/tasks/evidence/T005/qa/fidelity-probes-r2.txt` | PASS |
| 5 | O6 drift in scratch copies mounted as `/contract`: `respondError(423, "door_busy", …)` → 1 failed (`assert 409 == 423`); `unauthorized` renamed only in `http.cpp` → 1 failed; README State key renamed → 2 failed; real files → 12 passed. Path filter lists `garage.cpp`/`.h`, `settings.cpp`, `json.h`, `config.h` on push and pull_request | `docs/tasks/evidence/T005/qa/contract-r2.txt` | PASS |
| 6 | O1–O5, O7–O9 on the rebuilt dev simulator (code hashes equal to the repo): MAC `02:00:00:5E:1A:0A` for `garage-5e1a0a`; `rev` 1 after boot; OPTIONS → JSON 405 with `no-store`; errors carry `no-store`; `testing_wifi` answers the old network with `wifi_trying: true`, silent `SIM_RESTART_S`, then `wifi_up` + `wifi_changed` (as `net.cpp` `onConnected`, no `wifi_down` since `tryNetwork` clears `up` directly); bad hook body → 400 `invalid_hook_body`; README "Not simulated" and request-body section, Dockerfile comment, platform-ci skill updated | `docs/tasks/evidence/T005/qa/session-r2.txt`, `docs/tasks/evidence/T005/qa/fidelity-probes-r2.txt` | PASS |
| 7 | Full suites: backend lint + 325 tests (100 %), frontend lint + 128 tests, firmware host tests; PR #6 checks green (End-to-end pending at the time of the check) | `docs/tasks/evidence/T005/qa/full-r2.txt`, `docs/tasks/evidence/T005/qa/firmware-tests-r2.txt` | PASS |

### Observations (non-blocking)
- `sim/fwjson.py:76` parses the four `\u` digits with Python `int(…, 16)`, which accepts `_` (`\u0_7f` → 0x7F, 200);
  `strtoul` stops at `_` and the board refuses it (400 `invalid_name`). Sign, leading space and `0x` behave
  alike in both. No client sends this.
- `net.cpp` is not in the workflow path filter, though the simulator mirrors its boot `wifi_up`, the
  WiFi-change events and the id/MAC relation. Worth adding with the next touch.
- For phase 2: the board answers a non-ASCII `\u` escape in `name` with `invalid_name` / "Name must not be
  empty" (firmware message, faithfully reproduced), so the platform should send raw UTF-8 and map that
  error to its own message.

## After QA round 2
- The two notes taken up: `\u` escapes with `_` are refused as `strtoul` does (test added), and
  `net.cpp` (boot and WiFi events, id from the MAC) joins the Platform workflow path filter.
