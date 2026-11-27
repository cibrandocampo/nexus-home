# T012 — Frontend: dashboard and device page

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T010

## Context
The home page becomes the devices dashboard (user decision 2026-11-27: a card per device with its
state and quick actions), and each device has its own page with every entity and the type details
the board's own web page shows.

## Objective
A `user` opens the app and sees every device with its door and light state and buttons to operate
them; a tap opens the device page.

## Step 1 — Before coding
Read `platform-frontend` and `frontend-design`; run `modern-web-guidance` (in Docker) for the patterns
used here (status indicators, confirmation dialog, live-updating regions and their accessibility).

## Step 2 — API layer (`src/devices/devicesApi.js`)
Query hooks: `useDevices()` (list, refetch every 2 s while visible), `useDevice(id)` (2 s), and
`useCommand()` (mutation; on success writes the returned state into both caches). MSW handlers for
tests.

## Step 3 — Dashboard (`pages/HomePage.jsx` → devices)
One card per device: name, online dot (offline greyed, with "last seen …" in the user's time zone),
the cover entity (state, time since the last change, stopped part way, failed close alert) with
Open / Close / Stop, the light (state, remaining time) with On / Off. Door commands ask for
confirmation (a modal naming the device and the action; the plan's rule: the door is a house
entrance). Errors from the command translate their code (`door_busy`: "The door is moving, try again
in a moment"; `device_offline`, `device_unreachable`, `device_token_invalid`). Empty state: no devices
→ a message, and for admins a link to add one (T014's page).

## Step 4 — Device page (`/devices/:id`)
Generic entity cards (cover, light with a duration choice: default, 10 min, 1 h, no timer;
binary_sensor; sensor with unit) plus device info (model, version, modem, WiFi signal, uptime, IP,
online). Garage details from the driver: who moved the door last (`last_source`), the failed-close
alert, light level with day/night icon, time since the last door change. A link to the device's
history (T013).

## Step 5 — i18n and tests
Every string and every new error code (T006–T011's list) in `en`, `es`, `gl`. Tests (Vitest + Testing
Library + MSW): cards render each state (closed, opening, open stopped part way, close failed,
offline), confirmation before a door command, no confirmation for the light, error code → message,
the `user` role sees no admin links.

## DoD
1. `make lint-frontend test-frontend` pass with coverage at the template's threshold.
2. `make build-frontend` passes.
3. In the dev stack (browser, Claude in Chrome): the dashboard shows both simulators; Open on one asks
   for confirmation, then shows `opening` and `open` ~20 s later (or faster with `SIM_SPEED`); screenshots
   in light and dark mode, desktop and mobile width.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-frontend test-frontend` | `tests.txt` | 0 failures |
| 2 | Build | `make build-frontend` | `build.txt` | success |
| 3 | Browser | dev stack + Chrome | `dashboard-*.png` | states and flow as described |

## Files
| File | Action |
|------|--------|
| `platform/frontend/src/devices/*` (api, cards, entity components) | Create |
| `platform/frontend/src/pages/HomePage.jsx`, `pages/DevicePage.jsx` (+ tests, CSS modules) | Modify / create |
| `platform/frontend/src/App.jsx`, `components/AppLayout.jsx`, `components/BottomNav.jsx` | Modify |
| `platform/frontend/src/i18n/{en,es,gl}.json` | Modify |
