---
name: platform-ci
description: GitHub Actions of the nexusHome platform — what platform.yml, the weekly rebuild, the disposable-domains sync and Dependabot do, path filters, platform-v releases and how Docker Hub publishing is gated. Use when touching .github/ for the platform or diagnosing a red platform run.
---

# Platform CI — GitHub Actions

## Principle

CI runs the same Docker commands as a laptop: no `setup-python`, no `setup-node`, no host `npm`/`pip`.
Each job builds the dev images or the production image and runs inside them, from `platform/`
(`defaults.run.working-directory`). If a CI step and a `make` target do the same thing, they must
stay in sync. The garage firmware has its own workflow (`ci.yml`).

## `platform.yml`

Runs on PRs to main and pushes to main **that touch `platform/**` or the workflow** (GitHub evaluates a
PR's paths on its whole diff), and on published releases. Every job carries
`if: github.event_name != 'release' || startsWith(github.event.release.tag_name, 'platform-v')`:
`paths` does not apply to releases, and firmware releases (`garage-v…`) must not build the platform.

```
backend ──┐
          ├──► e2e ──► image
frontend ─┘
audit (advisory, continue-on-error)
```

| Job | Does | Local equivalent (in `platform/`) |
|---|---|---|
| `backend` | builds the dev backend; `ruff check` + `ruff format --check`; pytest with coverage against Postgres + Mailpit | `make lint-backend coverage-backend` |
| `frontend` | eslint, prettier, vitest with coverage, production build; Prettier check of `e2e/` | `make lint-frontend test-frontend build-frontend lint-e2e` |
| `audit` | `pip-audit` on `requirements.txt`, `npm audit --omit=dev --audit-level=high`; never blocks | — |
| `e2e` | starts the production `db` from `docker-compose.yml` with data on disk; `make e2e`; uploads `platform/e2e/artifacts/` on failure (14 days) | `make e2e` |
| `image` | buildx of `platform/` with `APP_VERSION` = `git describe --match 'platform-v*'` without the prefix; push or build only (below) | `make build` |

Notes: the runner's uid differs from the image users — the backend job passes `HOST_UID`/`HOST_GID`,
the frontend job makes `frontend/` writable for the image's `node` user. `permissions: contents: read`.
Concurrency cancels superseded runs of the same PR only.

## Publishing to Docker Hub (`cibrandocampo/nexus-home`)

Pushes only when **all** hold: secrets `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN`, variable
`DOCKER_IMAGE`, and the event is a push to main or a published platform release.

| Event | Tags | Platforms |
|---|---|---|
| push to main (touching `platform/`) | `latest` | amd64, arm64 |
| release `platform-v1.2.0` | `1.2.0`, `stable` (not for a prerelease) | amd64, arm64 |
| PR / no credentials | none (build only) | amd64 |

`docker-compose.yml` deploys `${APP_TAG:-stable}`, so production follows platform releases. Tags use
`docker/metadata-action` with `flavor: latest=false` and
`type=match,pattern=platform-v(\d+\.\d+\.\d+.*),group=1`.

## Other workflows

- `platform-weekly-rebuild.yml` (Mondays, manual too): rebuilds `latest` from main and `stable` +
  version from the newest non-prerelease `platform-v…` release, without cache, so base-image fixes reach
  the published tags. Skips without credentials or without a platform release.
- `platform-disposable-domains.yml` (Sundays, manual too): refreshes
  `platform/backend/app/auth/disposable/disposable_email_domains.txt` and opens a PR when it changed.
- `.github/dependabot.yml`: weekly PRs for pip (`/platform/backend`; then run `make lock` on the branch:
  requirements are hashed), npm (`/platform/frontend`, `/platform/e2e`), Docker and compose images (one
  grouped PR across `/platform`, `/platform/dev`, `/platform/e2e`) and actions; ESLint majors are held
  until eslint-plugin-jsx-a11y supports them. Bump the Playwright image in `e2e/Dockerfile` together with
  `@playwright/test`.

## Changing workflows

- Validate with actionlint (Docker), from the repository root:
  `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest`.
- Pin actions to their current major (`actions/checkout@v7`, `docker/build-push-action@v7`, …).
- Secrets never in `if:` at job level — map them to `env` (`CAN_PUSH`) and test that.
- A red run: read the failing step's log (`gh run view <id> --log-failed`); for e2e download the
  `playwright-report` artifact and open `report/index.html`; a trace opens in the browser at
  https://trace.playwright.dev (drop the `trace.zip`; it is processed locally in the page).
