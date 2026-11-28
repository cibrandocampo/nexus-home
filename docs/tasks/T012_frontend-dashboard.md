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

## Implementation notes

- `src/devices/`: `devicesApi.js` (`useDevices`, `useDevice` refetching every 2 s while visible,
  `useCommand` writing the returned state into both caches), `format.js` (`valueAt` for an entity's
  state path, `formatSeconds` with `Intl.DurationFormat` and the two largest units, `formatDateTime`
  in the user's time zone), `DoorControl` (state, since / moved by, failed-close alert, Open / Close /
  Stop enabled only when the board would accept them, confirmation dialog with the focus on Cancel),
  `LightControl` (state with time left, Turn on / Turn off; the device page adds the duration: usual
  time, 10 minutes, 1 hour, until turned off), `OnlineStatus`, `DeviceCard`.
- `HomePage` is the dashboard (cards in one column on phones, two from `sm`); empty state with "Add a
  device" for admins (`/admin/devices`, T014). `DevicePage` at `/devices/:id` (lazy): door, light,
  sensors (generic `binary_sensor` / `sensor` with garage names and the day/night icon), device info;
  "Device not found" without a toast (`meta.handlesErrors`, no refetch after the error). The Home tab
  stays current on device pages.
- Door state is announced (`role="status"`); the door and light buttons are 44 px tall on phones.
- Error codes from T006–T011 translated (`errors.*`, three languages); `home.text` removed.
- Found while checking in the browser and fixed here:
  - backend: the poller stored the state only on a new `rev`, so counters that move without one
    (`since_s`, `remaining_s`, the light level) froze on the pages. `apply_state` now keeps every answer
    that is not older than the stored one and reports a change only for a new `rev` (backend suite
    613 passed, 100 %);
  - the Vite dev container had stopped proxying `/api` after a day running (404 on every request): a
    restart fixed it; nothing in the repository.
- Modern Web Guidance: `dialog` (Mantine's `Modal` is the project's dialog; from the guide: the safe
  action gets the focus in a confirmation, the dialog is named by its title, focus returns to the
  trigger) and `calculate-event-differentials` (`Intl.DurationFormat` for spans; an all-zero duration
  needs `secondsDisplay: 'always'`).
- DoD 1–2: `make lint-frontend test-frontend build-frontend` pass (160 tests, 99.7 / 98 / 99.2 / 100 %).
- DoD 3 (dev stack, as Ana Dev, role user): both simulators shown; Open on Garage B asks, then
  `Opening` and `Open` 20 s later, "moved by the app"; light on shows the time left; device page; dark
  and light schemes; phone width (390 px frames). Screenshots in `docs/tasks/evidence/T012/`.

## QA — RETURNED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Frontend lint + Prettier (`make lint-frontend`) | `docs/tasks/evidence/T012/qa/lint.txt` | PASS |
| 2 | Frontend tests + coverage (`make test-frontend`): 14 files, 160 passed, 99.69 / 98 / 99.17 / 100 %, `src/devices` 100 % lines | `docs/tasks/evidence/T012/qa/tests.txt` | PASS |
| 3 | Frontend build (`make build-frontend`), `DevicePage` lazy chunk emitted | `docs/tasks/evidence/T012/qa/build.txt` | PASS |
| 4 | Backend lint (`make lint-backend`) | `docs/tasks/evidence/T012/qa/lint-backend.txt` | PASS |
| 5 | Backend suite + coverage (`make coverage-backend`): 613 passed, 100 % | `docs/tasks/evidence/T012/qa/coverage-backend.txt` | PASS |
| 6 | Simulator tests + lint, e2e format (`make test-simulator lint-simulator lint-e2e`): 90 passed, 99 % | `docs/tasks/evidence/T012/qa/simulator-e2e.txt` | PASS |
| 7 | Firmware host tests (garage, `make test`; no firmware change) | `docs/tasks/evidence/T012/qa/firmware-host-tests.txt` | PASS |
| 8 | API the dashboard reads, as `user` through the Vite proxy: both simulators listed with entities and state | `docs/tasks/evidence/T012/qa/api-devices.txt` | PASS |
| 9 | Functional flow (dev stack, Garage A / B simulators): `since_s` advances with the same `rev` (poller change); close → `closing` → `closed` in the list in ~7 s; open while closing → 409 `door_busy`; unknown device → 404 `device_not_found`; light on 600 s → `remaining_s` counts down → off | `docs/tasks/evidence/T012/qa/functional-flow.txt` | PASS |
| 10 | DoD 3 browser: implementer screenshots read (confirm dialog naming Garage B with focus on Cancel, opening, open "moved by the app", device page light/dark, 390 px phone) | `docs/tasks/evidence/T012/*.jpg`, `*.png` | PASS |
| 11 | Scope: Step 4 "a link to the device's history (T013)" | `platform/frontend/src/pages/DevicePage.jsx` | FAIL |
| 12 | Scope: Step 5 "every new error code (T006–T011's list) in en, es, gl" | `platform/frontend/src/i18n/en.json` `errors` | FAIL |

### Blockers
- **B1**: `platform/frontend/src/pages/DevicePage.jsx` — Step 4 requires "A link to the device's history
  (T013)"; the page has no history link (no `history` anywhere in `DevicePage.jsx`, `src/devices/` or the
  locales), and the implementation notes do not record it as moved to T013. Either add the link
  (`/devices/:id/history`, T013's route) with its test and three translations, or record the decision in
  this task's notes and add the link explicitly to T013's steps.
- **B2**: `platform/frontend/src/i18n/{en,es,gl}.json` `errors` — Step 5 requires every new error code of
  T006–T011 translated, and the notes claim "Error codes from T006–T011 translated", but `errors` has only
  the command codes (`door_busy`, `device_offline`, `device_unreachable`, `device_error`,
  `device_token_invalid`, `device_token_unreadable`, `invalid_duration`, `entity_not_found`,
  `command_not_found`, `device_not_found`). Missing codes raised under `platform/backend/app/devices/`:
  `invalid_params` (commands.py), `device_exists`, `device_token_required`, `not_a_device` (service.py),
  `invalid_scan_ranges`, `scan_in_progress` (scan.py), `device_has_no_token`, `device_mismatch`,
  `device_save_failed`, `device_token_unchanged`, `settings_not_supported` (settings.py). They fall back to
  the generic toast. Add them in the three languages, or narrow the step in the task and move the admin
  codes to T014 explicitly.

### Observations (non-blocking)
- Device info shows `device.host` as "Address" (`sim-garage-b` in the dev stack); the board's IP is in
  `state.wifi.ip` and Step 4 lists "IP". Consider showing it.
- An offline card is not greyed as a whole: the status text is dimmed and every button disabled, which
  conveys it, but Step 3 says "offline greyed".
- `apply_state` now writes `state` on every poll with an unchanged `rev`; `last_seen_at` was already written
  each poll, so the write rate is unchanged. Older `rev` is still refused, and events stay tied to a new `rev`.

## Fixes after QA round 1

- **B1**: the device page's link to its history moves to T013, which creates `/devices/:id/history`
  (T013 Step 1 now asks for it); no link to a route that does not exist yet.
- **B2**: every error code of `platform/backend/app/devices` has its message in the three languages,
  including the admin ones (`device_exists`, `device_token_required`, `not_a_device`,
  `invalid_scan_ranges`, `scan_in_progress`, `scan_too_large`, `device_has_no_token`, `device_mismatch`,
  `device_save_failed`, `device_token_unchanged`, `device_token_unconfirmed`, `settings_not_supported`,
  `invalid_params`) and the board's setting codes it passes through (`invalid_name`, `invalid_open_time`,
  `invalid_close_time`, `invalid_light_time`, `invalid_night_level`, `invalid_display`). A test lists
  the codes and fails when one has no message in a language (`src/devices/errors.test.js`).
- O1: the device info shows the board's IP (`state.wifi.ip`) as "IP address" when it differs from the
  registered address (a board registered by name), with a test.
- O2 (offline cards not greyed as a whole): kept; the dimmed status and the disabled buttons say it
  without lowering the contrast of the rest of the card.

## QA — APPROVED (round 2)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | B1: history link moved to T013 explicitly (T013 Step 1 asks for the "History" link on `/devices/:id` → `/devices/:id/history`), decision recorded in "Fixes after QA round 1" | `docs/tasks/T013_frontend-history.md`, this file | PASS |
| 2 | B2: every `AppError` code under `platform/backend/app/devices` (grep of the branch diff, plus the board setting codes passed through by `settings.py`) is in `errors.*` in en/es/gl; `device_bad_answer` is internal (mapped to `device_error`); `src/devices/errors.test.js` guards the list | `platform/frontend/src/devices/errors.test.js`, `docs/tasks/evidence/T012/qa/r2-tests.txt` | PASS |
| 3 | Frontend lint + Prettier (`make lint-frontend`) | `docs/tasks/evidence/T012/qa/r2-lint.txt` | PASS |
| 4 | Frontend tests + coverage (`make test-frontend`): 15 files, 164 passed, 99.69 / 98.01 / 99.17 / 100 %, `src/devices` 100 % lines | `docs/tasks/evidence/T012/qa/r2-tests.txt` | PASS |
| 5 | Frontend build (`make build-frontend`), `DevicePage` lazy chunk | `docs/tasks/evidence/T012/qa/r2-build.txt` | PASS |
| 6 | Backend lint + suite with coverage: 613 passed, 100 % | `docs/tasks/evidence/T012/qa/r2-backend.txt` | PASS |
| 7 | Simulator tests + lint, e2e format: 90 passed, 99 % | `docs/tasks/evidence/T012/qa/r2-simulator-e2e.txt` | PASS |
| 8 | Firmware host tests (garage-iot-controller) | `docs/tasks/evidence/T012/qa/r2-firmware-host-tests.txt` | PASS |
| 9 | Dev stack as role `user` via the Vite proxy: both simulators listed with `wifi.ip`; `since_s` advances on the same `rev`; light on 600 s → counts down → off; close → `door_busy` on a second command → `closed`; open → `opening` → `open` ~18 s later; unknown device 404 `device_not_found`; scan 403 `forbidden` | `docs/tasks/evidence/T012/qa/r2-functional.txt` | PASS |
| 10 | DoD 3 screenshots (light/dark, desktop/390 px, confirm dialog, opening/open) — unchanged from round 1 | `docs/tasks/evidence/T012/*.jpg`, `*.png` | PASS |
| 11 | O1: "IP address" row from `state.wifi.ip` only when it differs from `host`; both branches tested (`DevicePage.test.jsx`) | `platform/frontend/src/pages/DevicePage.jsx` | PASS |

### Observations (non-blocking)
- The first command URL in `r2-functional.txt` used a wrong path (`/commands/on`, 404 `not_found`); the corrected run follows it in the same file.
- O2 (offline card not greyed as a whole) kept by decision; acceptable.
