# T014 — Frontend: scan, add, remove and device settings (admin)

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T012, T007, T011

## Context
Admins register boards (scan or by IP), remove them, change their settings, restart them and manage
their token, from the platform's admin area.

## Objective
An admin can go from an empty platform to a registered, configured board without leaving the app.

## Step 1 — Admin devices page (`/admin/devices`)
- The registered devices (name, id, IP, version, online) with Remove (confirmation naming the
  device) and a link to its settings.
- Scan: the ranges (prefilled from `GET /api/devices/scan-ranges`, editable), Scan button with progress
  (it takes seconds), results with Add for unregistered ones. Add asks for the token, with a note that a
  board without one gets a new token from the platform (user decision 2026-11-27). `scan_in_progress`,
  `scan_too_large` shown translated.
- Add by IP: host + optional token.

## Step 2 — Device settings (`/admin/devices/:id`)
The driver's form (name, open/close/light times, night level, LED matrix) with the board's ranges and
the name's byte limit (counted in UTF-8 bytes, as the board does), Save sending only changed fields;
Restart (confirmation; `door_busy` translated); Token: Rotate (confirmation: the board's own web page
will need the new token) and Show (reveals it once, with copy); Edit host/token. Errors translated.

## Step 3 — Navigation, i18n, tests
Admin menu entry next to Users. Strings and codes in the three languages. Tests: scan flow (progress,
results, add with and without token), remove confirmation, settings validation (ranges, "ñ" byte count),
only changed fields sent, rotate and reveal, a `user` cannot reach these routes.

## DoD
1. `make lint-frontend test-frontend` pass; `make build-frontend` passes.
2. Dev stack in the browser: empty platform → scan finds both simulators → add one with its token →
   the dashboard shows it → change its light time → rotate its token; screenshots.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-frontend test-frontend` | `tests.txt` | 0 failures |
| 2 | Browser | dev stack + Chrome | `admin-*.png` | full flow as described |

## Files
| File | Action |
|------|--------|
| `platform/frontend/src/pages/admin/DevicesPage.jsx`, `DeviceSettingsPage.jsx` (+ tests, CSS) | Create |
| `platform/frontend/src/pages/admin/devicesAdminApi.js` | Create |
| `platform/frontend/src/App.jsx`, navigation components, `i18n/*.json` | Modify |
