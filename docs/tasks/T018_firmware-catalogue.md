# T018 — Firmware catalogue: GitHub sync and uploads

**Plan**: docs/plans/platform-middleware.md (phase 3) · **Depends on**: T017

## Context
The platform keeps the firmware it can install: stable releases and pre-releases from GitHub, and
files an admin uploads. They live in a data volume and are verified before they are offered.

## Objective
`/api/firmware` lists the firmware per device type; a sync (every `FIRMWARE_CHECK_HOURS` and on demand)
downloads new release assets and checks `SHA256SUMS`; admins upload `.ota` or `.bin` files.

## Step 1 — Settings and storage
`GITHUB_REPO` (default `cibrandocampo/nexus-home`), `FIRMWARE_CHECK_HOURS` (default 6),
`FIRMWARE_DIR` (default `/data/firmware`). Production compose: a volume `$DATA_PATH/firmware:/data/firmware`
(the app stays read-only otherwise); dev and e2e compose mount one too. `.env.example`,
`docs/configuration.md` (and the backups section: the files can be downloaded again, uploads cannot).

## Step 2 — Model and migration
`FirmwareFile`: `device_type`, `version`, `source` (`release` / `upload`), `test` (pre-release or upload),
`sha256`, `size`, `filename` (stored `.ota`), `release_url`, `notes` (release body, trimmed), `published_at`,
`uploaded_by` (FK users, `SET NULL`), `created_at`; unique `(device_type, version, source)`.

## Step 3 — Sync (`firmware/sync.py`)
GitHub REST `GET /repos/{repo}/releases` (no token: public repository; `User-Agent: nexusHome-platform`,
ETag kept to spare the rate limit). For each release whose tag is `<type>-v<version>` with a known driver
(`garage`): skip if stored; download `SHA256SUMS` and `<type>-<version>.ota`, verify the hash and the
`.ota` header (T017 `check_ota`), store under `FIRMWARE_DIR/<type>/<version>.ota` (written to a
temporary name, then renamed). Draft releases ignored; deleted releases keep their stored file. Runs in
the scheduler every `FIRMWARE_CHECK_HOURS` and from `POST /api/firmware/sync` (admin; one at a time;
409 `sync_in_progress`; rate limited); answers `{added: [...], checked_at}`. Network errors are logged
and answered 502 `github_unreachable`.

## Step 4 — API
- `GET /api/firmware?type=garage` (admin): stable releases newest first, then test versions; each with
  version, source, test, size, sha256, release_url, notes, published_at, uploaded_by name.
- `POST /api/firmware/upload` (admin, multipart: `type`, `version`, `file`): `.ota` checked, `.bin`
  converted (T017) in a thread; ≤ 1 MB; version `^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$`;
  stored as `source=upload`, `test=true`; 409 `firmware_exists`, 400 `invalid_firmware`, 413
  `file_too_large`. Rate limited.
- `DELETE /api/firmware/{id}` (admin): uploads only (403 `release_firmware` for releases).

## Step 5 — Tests
Sync with a fake GitHub (httpx MockTransport): new release stored, pre-release marked test, bad hash
refused (nothing stored), unknown type skipped, draft skipped, ETag 304, network error; upload of each
kind and every error; listing order; delete rules; roles.

## DoD
1. `make lint-backend coverage-backend` pass, coverage ≥ 95 %.
2. Dev stack: `POST /api/firmware/sync` against the real GitHub answers (with no release yet, an empty
   `added`); an upload of `dist/garage-2.0.6.bin` is converted and listed as test.
3. After the first real release (T016 DoD 4, user), a sync downloads it and verifies it.

## Files
| File | Action |
|------|--------|
| `platform/backend/app/firmware/{models,schemas,router,service,sync}.py` | Create |
| `platform/backend/app/core/config.py`, `core/scheduler.py`, `main.py`, `models.py`, `requirements.in` (`python-multipart`) | Modify |
| `platform/backend/alembic/versions/<date>_firmware_files.py` | Create |
| `platform/docker-compose.yml`, `dev/docker-compose.yml`, `e2e/docker-compose.yml`, `.env.example`, `docs/configuration.md` | Modify |
| `platform/backend/tests/test_firmware_*.py` | Create |
