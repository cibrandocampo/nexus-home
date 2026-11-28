# T021 — Frontend: firmware

**Plan**: docs/plans/platform-middleware.md (phase 3) · **Depends on**: T020

## Objective
Admins see each device's firmware (installed, latest, update available), install a version (test
versions apart, a downgrade warned), follow it to the end, and manage the catalogue (sync, upload,
delete uploads). Users see the installed version and, when one exists, that an update is available.

## Steps
- Device settings page: a "Firmware" section: installed and latest version with release notes link;
  "Install…" dialog: stable versions, then a "Test versions" group; a downgrade or a test version says
  so before confirming; progress while it runs (polling the device's firmware every 2 s), result
  message, last update shown.
- `/admin/firmware`: the catalogue per type (version, release or upload, test badge, size, date, notes
  link), "Check GitHub now", upload (type, version, `.ota` / `.bin`), delete uploads.
- Dashboard / device page: "Update available" badge for admins next to the version.
- All new error codes translated; tests for each flow; `make e2e` still green.

## DoD
1. `make lint-frontend test-frontend build-frontend` pass; `make e2e` passes.
2. Dev stack in the browser: upload a build, install it on a simulator, watch it finish; screenshots.
