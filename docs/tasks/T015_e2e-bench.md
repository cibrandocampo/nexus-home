# T015 — End-to-end tests against the simulator; bench-board checks; docs

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T013, T014

## Context
Phase 2 ends with its flows proven on the production image against the simulator in CI, and once by
hand against the bench board on the LAN.

## Objective
`make e2e` covers scan, add, commands, history and settings against `sim-garage`; the bench board
passes the same flow by hand; the docs describe the devices features.

## Step 1 — E2E stack
- `e2e/docker-compose.yml`: a network with a fixed subnet (e.g. `172.31.250.0/24`) and a fixed address
  for `sim-garage`, so the scan has a range to probe; `SCAN_RANGES` set to that subnet (a /28 around the
  simulator keeps it fast); `DEVICE_TOKEN_KEY` test value; `POLL_INTERVAL_S` 1. A second simulator
  without a token for the "new board" path.
- Hooks: the specs drive the simulators through `/sim/*` from the Playwright container.

## Step 2 — Specs (`e2e/tests/devices.spec.js`)
1. Admin scans, finds both simulators, adds the one with a token (and a wrong token first: error), and
   the tokenless one (gets a token).
2. A `user` opens the dashboard, opens the door (confirmation), sees `opening` then `open`;
   `door_busy` on an immediate close is shown translated.
3. Light on with a duration from the device page; remaining time shown.
4. A button press on the simulator (`/sim/button`) appears on the dashboard within a few seconds and
   in the history with source "button"; the platform's commands show the user.
5. `/sim/offline` → the card shows offline, then back online.
6. Admin changes the light time and rotates the token; the device keeps working.
7. A `none` user and a `user` cannot reach the admin pages.

## Step 3 — Bench board (by hand, with the dev stack; never the production board)
Scan `10.1.3.0/24` (finds both boards; only the bench one is added), add `garage-33ad84`, operate the
light and a door pulse (no motor wired), check the history, change and revert a setting, restart it
and see the reboot. The production board `garage-3562d4` may appear in the scan and is not added.

## Step 4 — Docs
`platform/README.md` (devices features), `docs/configuration.md` (all new variables, LAN access notes
for the Synology: bridge network reaches the LAN), garage README "Platform" pointer, CHANGELOG
(Unreleased), the plan's phase 2 marked done.

## DoD
1. `make e2e` passes (all specs, the template's included) twice in a row.
2. The Platform workflow is green on the PR.
3. Bench board flow as in Step 3, recorded with screenshots and the API answers.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | E2E | `make e2e` ×2 | `e2e-1.txt`, `e2e-2.txt` | all pass |
| 2 | CI | `gh pr checks` | `ci.txt` | all green |
| 3 | Bench | dev stack + Chrome + curl | `bench/*` | each step as described |

## Files
| File | Action |
|------|--------|
| `platform/e2e/docker-compose.yml`, `e2e/tests/devices.spec.js`, `e2e/tests/helpers.js` | Modify / create |
| `platform/README.md`, `platform/docs/configuration.md`, `platform/CHANGELOG.md` | Modify |
| `devices/garage-iot-controller/README.md`, `docs/plans/platform-middleware.md` | Modify |

## Implementation notes

- First: the e2e suite had been red on the PR since T012 (the home page's title changed from
  "Welcome" to "Home"; the specs, `global-setup.js` and a Spanish check still expected the old one,
  and the frontend tasks' checks had not run `make e2e`). Fixed in its own commit (`4a78d82`), before
  this task's specs.
- `e2e/docker-compose.yml`: a fixed subnet `172.31.250.0/24` (dynamic addresses from its upper half),
  `sim-garage` (`garage-e2e001`, token) at `.10` and `sim-garage-new` (`garage-e2e002`, no token) at
  `.11`; the server scans `172.31.250.0/28` (1 s per address), polls every second and reads logs every
  5 s; the Playwright runner gets the simulators' URLs and the token, and waits for both.
- `e2e/tests/devices.spec.js` (serial, the boards are added once):
  1. the admin follows "Add a device" from the empty dashboard, scans (2 devices among 14 addresses),
     adds E2E Garage (a wrong token first: refused with its message) and New Garage without a token,
     and creates the user account for the next specs;
  2. the user opens the door (confirmation, focus on Cancel), sees Opening, Open "moved by the app",
     then closes it;
  3. the user turns the light on for 10 minutes from the device page and off again;
  4. a button press on the simulator shows on the dashboard ("moved by the button") and in the history
     ("button or remote"), next to the user's own command ("by Ana Door");
  5. `/sim/offline` for 25 s: the card shows offline (buttons disabled), then online again;
  6. the admin changes the light time and the token; the old token is refused by the board, and a
     command from the dashboard still works;
  7. a `user` gets "Page not found" at `/admin/devices` and has no Devices tab; an account without a
     role is sent to "Waiting for access".
  `door_busy` is not reached from the UI (the buttons offer only what the board accepts); it is
  covered by the frontend and backend tests.
- Docs: `platform/README.md` (what it does, the dev simulators), `docs/configuration.md` ("Reaching the
  devices": LAN access from the bridge network, SCAN_RANGES, DHCP, one connection per board; backups:
  keep `DEVICE_TOKEN_KEY`), `CHANGELOG.md` (Unreleased: devices, simulator, PostgreSQL 19), garage
  README "Platform" section, the plan's phase 2 marked implemented.
- DoD 1: `make e2e` twice in a row, 22 passed each (`e2e-1.txt`, `e2e-2.txt`), format check clean.
- DoD 2: the Platform workflow on the PR (after the push).
- DoD 3: **NEEDS USER** — the bench board is unplugged (no `/dev/ttyACM0`, 10.1.3.114 silent).

## QA — APPROVED (round 1)

**Date**: 2026-11-28

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | E2E compose file valid | `docs/tasks/evidence/T015/qa/e2e-config.txt` | PASS |
| 2 | E2E specs format (`make lint-e2e`) | `docs/tasks/evidence/T015/qa/lint-e2e.txt` | PASS |
| 3 | `make e2e` run 1: 22 passed (7 device specs), retries 0 | `docs/tasks/evidence/T015/qa/e2e-1.txt` | PASS |
| 4 | `make e2e` run 2: 22 passed, retries 0 | `docs/tasks/evidence/T015/qa/e2e-2.txt` | PASS |
| 5 | Backend lint / coverage: 613 passed, 100 % | `docs/tasks/evidence/T015/qa/lint-backend.txt`, `coverage-backend.txt` | PASS |
| 6 | Frontend lint / tests: 208 passed, thresholds met | `docs/tasks/evidence/T015/qa/lint-frontend.txt`, `test-frontend.txt` | PASS |
| 7 | Simulator lint / tests (contract with the changed garage README): 90 passed, 99 % | `docs/tasks/evidence/T015/qa/lint-simulator.txt`, `test-simulator.txt` | PASS |
| 8 | Garage firmware host tests | `docs/tasks/evidence/T015/qa/firmware-test.txt` | PASS |
| 9 | DoD 2: Platform workflow on PR #9 | `docs/tasks/evidence/T015/qa/ci.txt` | PASS for 4a78d82; T015 is not pushed yet, re-check at `/push` |
| 10 | DoD 3: bench-board flow | — | NEEDS USER (board unplugged) |
| 11 | Docs: README, configuration, CHANGELOG, garage README, plan | diff review | PASS |

### Observations (non-blocking)
- Step 2.2's `door_busy` is not reached from the UI (the door control offers only what the board
  accepts); it is covered by `HomePage.test.jsx`, `devices/errors.test.js` and the backend command tests.
- `e2e/tests/helpers.js` was listed as Modify but needed no change; the existing helpers were enough.
- `docs/configuration.md` "Reaching the devices" covers bridge-network LAN access generically, not
  Synology by name. It is accurate, but a one-line Synology mention would match Step 4 word for word.
- `platform/README.md`: the new dev-stack sentence runs past the usual line width (cosmetic).
- The dev stack was left running and untouched; the e2e project tore itself down (`down -v`) both times.
