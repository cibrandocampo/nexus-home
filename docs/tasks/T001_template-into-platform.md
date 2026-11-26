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
