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
