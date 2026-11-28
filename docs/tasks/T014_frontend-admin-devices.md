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

## Implementation notes

- `/admin/devices` (`DevicesPage`, lazy, admin): registered devices (name to their settings, id,
  address, firmware, online badge, "⋯" menu with Settings and Remove); "Add by address"; "Find devices on
  the network" with the configured ranges prefilled (editable; emptied → the configured ones), progress
  text while it runs, results with Add (or an "Added" badge, also right after adding one). Remove asks
  first and says the history goes too.
- Add dialog: address (read-only when it comes from a scan), optional token with the note that a board
  without one gets a token from the platform; a refused token reads "The device refused this token"
  (`DeviceErrorAlert` takes per-page wording).
- `/admin/devices/:id` (`DeviceSettingsPage`): the driver's form in a 30 rem column (name with a UTF-8
  byte counter, opening / close / light times and night level with their ranges, LED matrix), only the
  changed fields sent, "Nothing to save" otherwise; field errors from a 422's `details`; a board
  refusal translated. Restart (confirmation, focus on Cancel; `door_busy` explained in the dialog).
  Token: Show (a confirmation that the reveal is recorded, then the token and, after an unconfirmed
  rotation, the previous one, each with Copy), Change the token (confirmation), Change address or token.
  "Device not found" without a toast; `settings_not_supported` explained.
- Bottom nav: "Devices" tab for admins (`Router` icon) before Users.
- `src/pages/admin/devicesAdminApi.js` (mutations show their errors locally; the token reveal is a
  mutation, never cached), `src/devices/DeviceErrorAlert.jsx`, `src/devices/garageFields.js`.
- Tests: 24 new (both pages); a test fixture bug found on the way (one `HttpResponse` reused for
  several requests hangs the second: handlers build a fresh answer per request).
- DoD 1: lint, 205 tests (99.8 / 97.7 / 99.4 / 100 %), build.
- DoD 2 (dev stack, browser): Garage B removed first; scan of `172.19.0.0/24` found both simulators
  (Garage A "Added") in 8.4 s; Garage B added from the scan with its token; light time changed to 300
  (the simulator's `/settings` shows it) and the token changed (audit `settings update ok`, `token
  rotate ok`). The settings form was narrowed after the first screenshot. The test account was made
  admin for the run and put back to `user`; Garage B was put back on its `.env` token, host name and
  light time. Screenshots in `docs/tasks/evidence/T014/`.

## QA — RETURNED (round 1)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | `make lint-frontend` (eslint 0 warnings, prettier) | `docs/tasks/evidence/T014/qa/lint.txt` | PASS |
| 2 | `make test-frontend`: 20 files, 205 tests, 0 failures, no skips; coverage 99.78 / 97.69 / 99.44 / 100 %, new files 100 % lines | `docs/tasks/evidence/T014/qa/tests.txt` | PASS |
| 3 | `make build-frontend` (admin pages in their own lazy chunks) | `docs/tasks/evidence/T014/qa/build.txt` | PASS |
| 4 | i18n: 374 keys in en/es/gl, same key set; every `AppError` code of `backend/app/devices/` translated in the three | checked with jq (command in the QA run) | PASS |
| 5 | Dev stack, the page's API calls through the Vite proxy as admin: list (no token field, only `has_token`), scan ranges, `scan_too_large`, settings GET, `PATCH {light_s: 300}` and back to 120, 17 × "ñ" name → 422 `at most 32 bytes`, reveal `Cache-Control: no-store`, rotate 204 → simulator refuses the old token (401) and accepts the new one (200), audit rows hold neither token | `docs/tasks/evidence/T014/qa/api-flow.txt`, `api-restore.txt` | PASS |
| 6 | Scan of the dev Docker network finds both simulators (registered, ids 8 and 5); adding a registered host → `device_exists`; `/admin/devices` and `/admin/devices/8` served | `docs/tasks/evidence/T014/qa/api-scan-docker.txt` | PASS |
| 7 | Garage B put back: simulator and platform on the `.env` token, `previous_token` null, light time 120, both simulators online | `docs/tasks/evidence/T014/qa/api-restore.txt` | PASS |
| 8 | Browser flow (DoD 2): screenshots of the scan running, results, add dialog, added, settings saved, rotate confirmation | `docs/tasks/evidence/T014/*.jpg` | PASS (see observations) |
| 9 | Token not kept in memory after its dialog closes | `docs/tasks/evidence/T014/qa/mutation-cache.txt` | FAIL |
| 10 | Step 3 test list: scan progress | `platform/frontend/src/pages/admin/DevicesPage.test.jsx` | FAIL |

### Blockers
- **B1**: `platform/frontend/src/pages/admin/devicesAdminApi.js:39-41` (`useRevealToken`), and `:27`
  (`useAddDevice`), `:31` (`useUpdateDevice`) — the comment says the revealed token is "never cached",
  but a `useMutation` result and its variables stay in the `MutationCache` after the dialog unmounts
  until `gcTime` runs out (TanStack Query 5.108.4: 5 minutes in the browser). So the revealed token and
  previous token (`state.data`), and the token typed in Add / Change address or token
  (`state.variables`), stay in the page's memory for 5 minutes after the dialog is closed. Shown in
  `qa/mutation-cache.txt`: one second after the observer unsubscribes, the cache still holds
  `data: {"token": ...}` and `variables: {"host", "token"}`. Expected: these three mutations pass
  `gcTime: 0`, so the entry is dropped when its dialog closes, and a test checks that
  `queryClient.getMutationCache().getAll()` holds no token after the reveal dialog and the add dialog close.
- **B2**: `platform/frontend/src/pages/admin/DevicesPage.test.jsx` — Step 3 asks for a test of the scan
  "progress", but no test checks the "Scanning. It takes a few seconds." status
  (`DevicesPage.jsx:250-254`) while the scan runs, or that it goes away when the scan finishes. The lines
  run during the tests, which is why line coverage is 100 %, but nothing asserts on them. Expected: a
  test that keeps the scan request pending (for example a deferred MSW handler), checks that the status
  text is shown and the button is loading, then lets the request finish and checks that the text is
  gone and the results are shown.

### Observations (non-blocking)
- No test opens `/admin/devices/:id` as a `user`. The route is in the same `RequireRole min="admin"`
  group as `/admin/devices`, which is tested, so the risk is low. One assertion would cover it.
- The DoD 2 screenshots skip "the dashboard shows it" and the result of the rotation (only its
  confirmation is shown). Rows 5 to 7 here cover both through the API.
- The "Copied" state of `CopyButton` (`DeviceSettingsPage.jsx:189`) is not tested.
- QA process note: the first API run scanned the configured range (`10.1.2.0/23`, the LAN) and not only
  the Docker network. That probe only read the boards' discovery answer and reached the production
  board (`garage-3562d4`) read-only. Nothing was written to any LAN device.

## Fixes after QA round 1

- **B1**: the three mutations that carry a device token (reveal, add, change address or token) use
  `gcTime: 0`: TanStack drops them from the mutation cache as soon as their dialog unmounts (5 minutes
  by default). Tests: after the reveal dialog closes, neither the token nor the previous token is in the
  mutation cache; after an add with a typed token, the token is not either. Mutation check: without
  `gcTime: 0` both tests fail.
- **B2**: a test holds the scan request open and checks the "Scanning…" status and the button's loading
  state, then lets it finish and checks both are gone and the result shows.
- O1: a test opens `/admin/devices/1` as a `user` (Page not found).
- O2/O3 (screenshots of the dashboard after the add and of the rotation result; the "Copied" state):
  covered by the QA's API checks and the existing tests; not added.
- QA note on its own run: one scan of the configured `10.1.2.0/23` reached the LAN (read-only
  `GET /info`, including the production board); recorded, nothing written to any LAN device.
- 208 frontend tests pass; build passes.

## QA — APPROVED (round 2)

**Date**: 2026-11-27

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | B1: reveal, add and change address/token mutations use `gcTime: 0` (`devicesAdminApi.js`); scan, remove, settings, restart, rotate carry no token | `platform/frontend/src/pages/admin/devicesAdminApi.js` | PASS |
| 2 | B1 tests are effective: with `gcTime: 0` removed (in a throwaway copy inside the frontend container, repository untouched), the add-dialog and reveal tests fail with the token found in the mutation cache | `docs/tasks/evidence/T014/qa/round2/mutation-gcTime.txt` | PASS |
| 3 | B2: test holds the scan request open, asserts the "Scanning…" status and `data-loading`, then both gone and the result shown | `DevicesPage.test.jsx` "shows the scan running until it ends", `qa/round2/tests.txt` | PASS |
| 4 | O1: `/admin/devices/1` as a `user` → Page not found | `DeviceSettingsPage.test.jsx` "device settings page access", `qa/round2/tests.txt` | PASS |
| 5 | `make lint-frontend` (eslint, prettier) | `docs/tasks/evidence/T014/qa/round2/lint.txt` | PASS |
| 6 | `make test-frontend`: 20 files, 208 tests, 0 failures, no skips; coverage 99.78 / 97.71 / 99.44 / 100 %, `src/pages/admin` and `src/devices` 100 % lines | `docs/tasks/evidence/T014/qa/round2/tests.txt` | PASS |
| 7 | `make build-frontend` | `docs/tasks/evidence/T014/qa/round2/build.txt` | PASS |
| 8 | Dev stack: `/admin/devices` and `/admin/devices/8` served, API 401 without a session, Vite serves the fixed module | `docs/tasks/evidence/T014/qa/round2/stack.txt` | PASS |
| 9 | Round 1 rows 4-8 (i18n, API flow, Docker-network scan, restore, screenshots): the round 2 change is client-side only, those results stand | `docs/tasks/evidence/T014/qa/*.txt` | PASS |

### Observations (non-blocking)
- No dedicated test for the "Change address or token" dialog leaving its token out of the mutation
  cache; it uses the same `secret: true` path as the add dialog, which is tested.
- Round 1 O2/O3 (dashboard/rotation screenshots, "Copied" state) left as is, covered by the API checks.
- Backend and simulator suites were not re-run: this task touches only the frontend and the backend is
  unchanged since T013's QA.
