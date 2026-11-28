# T013 — Frontend: event history

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T012

## Context
The history the platform collects (T009) with the user who sent each command (T010) needs a page.

## Objective
Users see the history of one device (from its page) or of all devices, filtered by device, event type
and date range, in their time zone.

## Step 1 — Page (`/history`, and `/devices/:id/history`)
A paginated list, newest first: time (user's time zone; date headers per day), device, event (translated:
"Door opening", "Light on (10 min)", "Close failed (40 s)", "Night", …), source (button, remote, API,
sensor, auto) and the user's name when known ("Door opening · API · Ana"). Filters: device (global
page only), event type (multi-select), from/to dates; filters kept in the URL query.

A link "History" on the device page (`/devices/:id`, T012) leads to `/devices/:id/history` (moved here
from T012: the route is created by this task).

## Step 2 — i18n and tests
Event, source and reason names in the three languages (the list from the garage README "Event log").
Tests: rendering of each event family, the user name, filters update the query and the URL,
pagination, empty state.

## DoD
1. `make lint-frontend test-frontend` pass; `make build-frontend` passes.
2. Dev stack in the browser: after commands from T012's dashboard, the global history shows them with
   the user; filtering by "Door" hides the light events; screenshots desktop and mobile.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-frontend test-frontend` | `tests.txt` | 0 failures |
| 2 | Browser | dev stack + Chrome | `history-*.png` | events, user, filters |

## Files
| File | Action |
|------|--------|
| `platform/frontend/src/pages/HistoryPage.jsx` (+ test, CSS module) | Create |
| `platform/frontend/src/devices/historyApi.js`, `eventLabels.js` | Create |
| `platform/frontend/src/App.jsx`, navigation components, `i18n/*.json` | Modify |

## Implementation notes

- `/history` (every device, with a device filter) and `/devices/:id/history` (one device, "Back to
  …" link; the device page links to it: "See its history", moved here from T012). New bottom-nav tab
  "History" (role `user`); the Home tab stays current on `/devices/:id` only.
- `src/devices/historyApi.js` (`useEvents`: `/api/events` or `/api/devices/{id}/events`, 50 per page,
  the first page refreshed every 10 s), `days.js` (`startOfDay` for a calendar day in the user's time
  zone, correct on the days the clocks change; `dayOf`, `formatDay`, `formatTime`), `eventLabels.js`
  (the README's events grouped for the filter; titles with values: "Light on for 10 min", "The door
  did not close after 40 sec"; cause = source and reason in words).
- Filters (device, events, from, to, page) live in the URL query; a changed filter goes back to page
  1; malformed dates are ignored. "To" is inclusive: the request's `to` is the start of the next day.
- Day headings and times in the user's time zone; each entry: time, what happened, then device (global
  page), cause and "by <user>" (a user without a name: "by a user without a name").
- Empty states: "Nothing has happened yet." / "No events match these filters."; pagination with named
  controls.
- DoD 1: lint, 179 tests (99.7 / 97.8 / 99.3 / 100 %), build.
- DoD 2 (dev stack, as Ana Dev, phone width — the browser window could not be widened from here, the
  desktop layout is the same single column): the history shows the dev stack's commands "by Ana Dev";
  `?event=light_on&event=light_off` shows only light events. Screenshots in
  `docs/tasks/evidence/T013/`. The time column was widened after the first screenshot (12-hour times
  wrapped).

## QA — APPROVED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Lint and format (`make lint-frontend`) | `docs/tasks/evidence/T013/qa/lint.txt` | PASS |
| 2 | Frontend tests with coverage (`make test-frontend`): 179 passed; new files 100 % lines (`HistoryPage.jsx` 96.1 % branches, over thresholds) | `docs/tasks/evidence/T013/qa/tests.txt` | PASS |
| 3 | Build (`make build-frontend`), `HistoryPage` lazy chunk emitted | `docs/tasks/evidence/T013/qa/build.txt` | PASS |
| 4 | Full suites: backend 613 passed, 100 % coverage; simulator 90 passed | `docs/tasks/evidence/T013/qa/backend.txt`, `docs/tasks/evidence/T013/qa/simulator.txt` | PASS |
| 5 | i18n: en/es/gl have the same 293 keys; every README event, source and reason translated | `docs/tasks/evidence/T013/qa/i18n.txt` | PASS |
| 6 | DoD 2 (API, as Ana, the page's queries): global history shows commands with `user: Ana Dev`; the "Door" group filter returns only door events (40, no light); light filter only light; device filter, date range (`to` exclusive next day), empty future range, one-device history and page 2 all correct | `docs/tasks/evidence/T013/qa/api-queries.txt` | PASS |
| 7 | DoD 2 (browser): implementer's screenshots show the list "by Ana Dev", day heading, translated causes, light filter, History tab current | `docs/tasks/evidence/T013/history-mobile-dark.jpg`, `docs/tasks/evidence/T013/history-filter-light-mobile-dark.jpg` | PASS |
| 8 | DoD 2: desktop and light-scheme screenshots (QA has no browser; only mobile dark exist) | — | NEEDS USER |

### Observations        (non-blocking)
- `/devices/<unknown>/history`: the title renders as "History of " with an empty name and the only feedback is the global error toast from the events query; the device page shows a "Device not found" heading instead. Untested path.
- A `?page=` past the last page shows "Nothing has happened yet." (unfiltered) even though events exist; the pagination is still shown, so the user can recover.
- The "Door" filter in the UI means picking the six door events one by one (Mantine group labels are not selectable); the API result is the expected one.

## After QA round 1

- O1: the history of an unknown device shows "Device not found" with a link to the history of every
  device, without a toast (`meta.handlesErrors` on that query), tested.
- O2: a page past the last one says "There are no events on this page." with a "Go to the first page"
  button, tested.
- O3 (door events picked one by one in the filter) is kept: the groups name them, and the URL keeps the
  choice.
- NEEDS USER (desktop and light scheme screenshots): taken, `history-device-desktop-light.jpg`.
- 181 frontend tests pass; build passes.
