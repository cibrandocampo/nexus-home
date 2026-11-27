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
