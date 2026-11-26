# T001 — Template into `platform/`

**Plan**: docs/plans/platform-middleware.md (phase 1) · **Depends on**: none

## Context
The platform starts as a copy of `cibrandocampo/fastapi-react-template` (main `af8fea9`): login, users,
roles, profile, Docker, end-to-end tests. Everything after this task builds on it, so it must run
exactly as the template does, only renamed and living under `platform/`.

## Objective
`platform/` holds the template's app, renamed to nexusHome, and every template command (dev stack,
unit tests, linters, end-to-end suite, production image) passes from inside `platform/`.

## Step 1 — Copy
From a clean checkout of the template at `af8fea9` (`git -C ../fastapi-react-template archive af8fea9`),
copy into `platform/`: `backend/`, `frontend/`, `e2e/`, `dev/`, `Dockerfile`, `.dockerignore`,
`docker-compose.yml`, `Makefile`, `.env.example`, `docs/configuration.md` (as `platform/docs/`),
`CHANGELOG.md`, `LICENSE` is not copied (the repository's own applies).

Not copied: `CLAUDE.md`, `MEMORY.md`, `.claude/` (nexus-home has its own; T003 brings the stack skills),
`.github/` (T002), `docs/plans`, `docs/tasks`, `docs/screenshots`, `scripts/` (pre-commit hook: it
assumes the project is the repository root; not used here).

## Step 2 — Rename
- `.env.example`: `PROJECT_NAME=nexus`, `APP_NAME=nexusHome`, `DOCKER_IMAGE=cibrandocampo/nexus-home`.
- `frontend/src/i18n/{en,es,gl}.json` `app.name` → `nexusHome`; `frontend/index.html` `<title>`.
- Emails, README and docs that say the template's name or "myapp".
- `CHANGELOG.md` reset to an `Unreleased` section: "Platform created from fastapi-react-template af8fea9".

## Step 3 — Fit the repository
- Root `.gitignore`: what the template's `.gitignore` ignores, scoped to `platform/` (node_modules,
  coverage, `e2e/artifacts`, `data/`, `.env`). Check nothing generated shows in `git status`.
- `platform/TEMPLATE.md`: source repository and commit, what was not copied and why, and how a template
  fix is ported (by hand, with the template commit noted in the platform commit).
- `platform/README.md`: what the platform is (one paragraph, pointing to the plan), how to start it
  (`cd platform && make init`), and a pointer to `docs/configuration.md`.
- Ports stay the template's (15173, 18000, 15432, 18025, 11025): nothing else in nexus-home uses them.

## DoD
1. `cd platform && make init` brings the dev stack up; the frontend answers on :15173 with title
   nexusHome; sign-in as `ADMIN_EMAIL` works (curl `POST /api/auth/login/verify` with the password).
2. `make qa` passes (backend 100 % coverage, frontend tests, linters).
3. `make e2e` passes (15 specs).
4. `make build` builds `cibrandocampo/nexus-home:local`; `docker run --rm … preflight` refuses the
   example secret key (template behaviour).
5. `git status` after all of the above shows only the intended files; `grep -rni "myapp\|fastapi-react-template" platform`
   only finds `TEMPLATE.md` and `CHANGELOG.md`.

`make` is not installed on the host (needs `sudo apt install -y make` by the user); until it is, run
the same compose commands the targets run and say so in the evidence.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Dev stack and sign-in | `make init`, curl the title and the login | `dev.txt` | 200, title nexusHome, access token returned |
| 2 | Unit tests and linters | `make qa` | `qa.txt` | all pass, backend 100 % |
| 3 | End-to-end | `make e2e` | `e2e.txt` | 15 passed |
| 4 | Image | `make build`; preflight run | `image.txt` | built; preflight refuses the example key |
| 5 | Leftovers | `git status --short`; the grep | `leftovers.txt` | only intended files; grep as stated |

## Files
| File | Action |
|------|--------|
| `platform/**` | CREATE (copied, renamed) |
| `platform/TEMPLATE.md`, `platform/README.md` | CREATE |
| `.gitignore` | MODIFY |

## Implementation notes
- Copied with `git archive af8fea9` (176 files) plus `TEMPLATE.md` and `README.md`.
- The template's `.gitignore` is kept as `platform/.gitignore` (a nested ignore file, paths relative to
  `platform/`) instead of scoping it in the root one; `docs/tasks/evidence/` dropped from it (the root
  file ignores it). `git add -n platform` lists 178 files, nothing generated.
- Renamed: `.env.example` (`PROJECT_NAME=nexus`, `APP_NAME=nexusHome`, `DOCKER_IMAGE=cibrandocampo/nexus-home`),
  `app.name` in en/es/gl, `<title>`, backend default `app_name`, `App.test.jsx`, the configuration doc example.
- Makefile: header points to this repository's rule; `VERSION` uses `git describe --match 'platform-v*'`
  without the prefix; the `hooks` target is gone (no `scripts/`).
- The rename exposed a fragile end-to-end selector: `getByRole('link', { name: 'Home' })` also matched
  the brand link "nexusHome". Now `exact: true`. The same latent issue is in the template (any app
  name containing "Home"): port it back.
- `make` is not installed on the host: every check ran the targets' compose commands directly.

## QA — RETURNED (round 1)

**Date**: 2026-11-26

Reviewed `platform/` as committed in `6e1df45`. HEAD moved to `f30fd2d` (T002, T003) during this QA;
`git diff 6e1df45 HEAD -- platform` is empty, so the result applies to the T001 tree. `make` is not
installed: every check ran the compose/docker commands of the matching Makefile target.

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 0a | Copy complete: `git archive af8fea9` vs `git ls-files platform` (467 template files, 290 in the documented non-copied paths, 177 copied + `TEMPLATE.md` = 178) | `docs/tasks/evidence/T001/qa/copy-diff.txt` | PASS |
| 0b | Copy faithful: only 14 files differ, every hunk is a rename, the Makefile/e2e/`.gitignore` changes, or a comment (full diff) | `docs/tasks/evidence/T001/qa/content-diff.txt` | PASS |
| 1 | Dev stack (`make init` commands): 4 services healthy; :15173 → 200, `<title>nexusHome</title>`; `POST /api/auth/login/verify` with `ADMIN_EMAIL`/`ADMIN_PASSWORD` → 200, access token and refresh cookie; wrong password → 400 | `docs/tasks/evidence/T001/qa/dev.txt` | PASS |
| 2 | `make qa` commands: ruff, eslint + prettier, e2e prettier clean; backend 325 passed, 100 % (1135 stmts, 204 branches); frontend 128 passed in 11 files, thresholds met | `docs/tasks/evidence/T001/qa/qa.txt` | PASS |
| 3 | `make e2e` commands: 15 passed, stack torn down (`down -v`) | `docs/tasks/evidence/T001/qa/e2e.txt` | PASS |
| 4 | `make build` → `cibrandocampo/nexus-home:local` (user `app`, `app_name=nexusHome`); preflight and the image entrypoint refuse `.env.example` (`SECRET_KEY=change-me`, exit 1); a random key passes (control) | `docs/tasks/evidence/T001/qa/image.txt` | PASS |
| 5 | Leftovers: `git status --short platform` empty; nothing generated tracked; DoD grep only finds `TEMPLATE.md` and `CHANGELOG.md` | `docs/tasks/evidence/T001/qa/leftovers.txt` | PASS |
| 6 | Step 2 rename sweep for the template's placeholder names ("My App", default "App") | `docs/tasks/evidence/T001/qa/leftovers.txt` | FAIL |

### Blockers
- **B1**: `platform/.env.example:43` — Step 2 asks to rename "emails … that say the template's name";
  found `EMAIL_FROM=My App <no-reply@example.com>` (the template's placeholder name), so every email from
  a stack created with `make init` is sent as "My App" while `APP_NAME=nexusHome`. Expected
  `EMAIL_FROM=nexusHome <no-reply@example.com>`. The DoD grep misses it (`myapp` does not match `My App`).
  Evidence: `leftovers.txt`, "Step 2 rename sweep".
- **B2**: `platform/backend/app/core/config.py:13` changed the `app_name` default to `nexusHome`, but
  `platform/docs/configuration.md:30` still documents the default as `App`; the sender default kept the
  old name in code and docs (`config.py:37` `email_from = "App <no-reply@example.com>"`,
  `configuration.md:65`). Expected: the documented defaults match the code, and the `email_from` default
  uses the same name as `app_name` (`nexusHome <no-reply@example.com>`) in both places. Evidence:
  `content-diff.txt` (config.py hunk; no configuration.md hunk for line 30) and `leftovers.txt`.

### Observations (non-blocking)
- `platform/dev/docker-compose.yml:3` comment change is not listed in the implementation notes; and
  line 2 still says the Makefile passes `--env-file .env` "from the repository root" (now `platform/`).
- The Files table says root `.gitignore` MODIFY; it was left unchanged in favour of the nested
  `platform/.gitignore` (documented in the notes). Works: no tracked platform file matches an ignore rule.
  Note that the root Python ignore (`lib/`, `env/`, `build/`, `dist/`, `var/`) also applies under
  `platform/`: a future `platform/frontend/src/lib/` would be silently ignored (`git check-ignore` shows
  it); the template has the same `build/`/`lib/`-style risk.
- The e2e compose project is named `app-e2e` (the template default): running this suite and the
  template's at the same time on one host would collide.
- `copy-diff.txt` "gained +x" line is an artefact of the scratch extraction; git modes match (annotated).

## Fixes after QA round 1
- B1: `.env.example` `EMAIL_FROM=nexusHome <no-reply@example.com>`.
- B2: `config.py` `email_from` default and `docs/configuration.md` (`APP_NAME`, `EMAIL_FROM` defaults) say
  nexusHome, matching the code.
- Observations: the compose fallbacks are `${PROJECT_NAME:-nexus}` (production, dev, e2e: the suite's
  project is now `nexus-e2e`, no clash with the template's `app-e2e`); the dev compose comment says
  `--env-file .env` from `platform/`; `platform/.gitignore` re-includes the generic folder names the
  root Python ignore file excludes (`lib/`, `env/`, `var/`…; `git check-ignore` shows
  `platform/frontend/src/lib/x.js` tracked, `node_modules/`, `dist/`, `build/` still ignored); the
  Files table's root `.gitignore` row is superseded by the nested file (see the notes above).
- Re-checked: backend 100 % coverage, e2e suite with no failures.

## QA — RETURNED (round 2)

**Date**: 2026-11-26

Reviewed fix commit `7a3bc45` (8 files; `platform/` changes are only the ones listed under "Fixes after
QA round 1"). The checks the change touches were re-run; frontend code is unchanged.

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| B1 | `.env.example:43` `EMAIL_FROM=nexusHome <no-reply@example.com>` | `docs/tasks/evidence/T001/qa/round2/rename-sweep.txt` | PASS |
| B2 | `config.py:13,37` and `configuration.md:30,65` all say nexusHome (code and docs agree) | `docs/tasks/evidence/T001/qa/round2/rename-sweep.txt` | PASS |
| 1 | Rename sweep: no "My App" / "yourname" / default "App" left; DoD grep only `TEMPLATE.md`, `CHANGELOG.md`; `git status platform` clean | `docs/tasks/evidence/T001/qa/round2/rename-sweep.txt` | PASS |
| 2 | Backend lint, format, 325 passed, 100 % (1135 stmts, 204 branches); e2e Prettier clean | `docs/tasks/evidence/T001/qa/round2/backend.txt` | PASS |
| 3 | Compose fallbacks without `PROJECT_NAME`: `nexus`, `nexus-dev`, `nexus-e2e` | `docs/tasks/evidence/T001/qa/round2/compose-names.txt` | PASS |
| 4 | e2e rebuilt and run as project `nexus-e2e`: 15 passed, torn down, no e2e container left | `docs/tasks/evidence/T001/qa/round2/e2e.txt` | PASS |
| 5 | `git check-ignore`: `lib/`, `env/`, `var/`, `lib64/`, `target/`, `cover/` under `platform/` not ignored; `node_modules/`, `dist/`, `build/`, `coverage/`, `.coverage`, `.venv/`, `.env`, `e2e/artifacts/`, `data/`, caches, `*.egg-info` still ignored; no tracked file matches a rule | `docs/tasks/evidence/T001/qa/round2/gitignore.txt` | PASS |
| 6 | Documented defaults match the code after the fix | `docs/tasks/evidence/T001/qa/round2/rename-sweep.txt` | FAIL |

### Blockers
- **B3**: `platform/docs/configuration.md:29`. The fix changed the compose fallbacks to
  `${PROJECT_NAME:-nexus}` (`docker-compose.yml:5`, `dev/docker-compose.yml:5`, `e2e/docker-compose.yml:5`),
  but the table still gives `PROJECT_NAME` the default `app`. Expected: `nexus`. This is the same kind of
  code/docs mismatch as B2, introduced by this fix. Evidence: `rename-sweep.txt`
  ("compose project-name fallbacks") and `compose-names.txt`.

### Observations (non-blocking)
- The first e2e run (`round2/e2e-run1-interfered.txt`) failed in `global-setup.js:12` ("Welcome!" not
  shown). It shared a `nexus-e2e` db and mailpit that were already running when it started (compose
  reported them as "Running", not "Created"), so the admin had already been onboarded by another run.
  This was interference, not a code fault. Its `down -v` also removed that other stack. After checking
  that no `nexus-e2e` containers, volumes or networks were left, the re-run from a clean project passed
  15/15. Running two e2e suites at the same time on one host is unsafe; the fixed project name now
  makes that visible.
- Round-1 observations are resolved: the dev compose comment, the e2e project name and the gitignore
  re-includes. The root `.gitignore` row in the Files table is now explained in the fixes section.

## Fixes after QA round 2
- B3: `docs/configuration.md` documents `PROJECT_NAME` default `nexus`, as the compose fallbacks.

## QA — APPROVED (round 3)

**Date**: 2026-11-26

Reviewed fix commit `f7f9887` (in `platform/`, only `docs/configuration.md`, one line). Nothing the test
suites or the e2e suite cover changed, so neither was re-run; round 2's results stand (backend 100 %,
e2e 15/15).

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| B3 | `configuration.md:29` `PROJECT_NAME` default `nexus`, matching the three compose fallbacks | `docs/tasks/evidence/T001/qa/round3/defaults.txt` | PASS |
| 1 | Mechanical comparison of every documented default against the `Settings` defaults in `config.py` (read with `ast`), `.env.example`, and the compose fallbacks and overrides (all 3 files). 0 drift: every Settings field and every `.env.example` variable is documented. The one non-equal row, `DATABASE_URL`, is documented as built by compose, which is what the compose files do. | `docs/tasks/evidence/T001/qa/round3/defaults.txt` | PASS |
| 2 | Rename sweep and DoD grep unchanged (only `TEMPLATE.md`, `CHANGELOG.md`); `git status platform` clean | `docs/tasks/evidence/T001/qa/round3/defaults.txt` | PASS |

### Blockers
None.

### Observations (non-blocking)
- `POSTGRES_USER` / `POSTGRES_DB` stay `app` (`.env.example`, `configuration.md:44,46`, the `config.py`
  `DATABASE_URL` fallback): consistent everywhere, and Step 2 did not ask to rename them. Renaming them
  to `nexus` later would need a fresh dev database volume.
