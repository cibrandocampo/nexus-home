---
name: dev-workflow
description: Commands, toolchain and environment for nexusHome — building and testing firmware, devices on the LAN, the platform's dev stack (make targets, ports, migrations, dependencies, end-to-end suite), CI. Use when building, testing, flashing, debugging the toolchain or running anything in the project.
---

# Dev workflow — nexusHome

## Repository

```
devices/<device>/      one Arduino controller per device (firmware, tests, tools, docs)
platform/              the platform: FastAPI + React app managing the devices (see platform/README.md)
docs/plans/            feature plans          docs/tasks/  task files + INDEX.md
.github/workflows/     CI
```

## Firmware (garage: `devices/garage-iot-controller`)

Everything runs in the toolchain image (`docker/Dockerfile`: Debian, `g++`, `python3`, `arduino-cli`
1.6.0 with checksum, core `arduino:renesas_uno` 1.6.0). Run `make` from the device folder; the image is
built on first use, the project is bind-mounted at `/work` and the container runs as you.

```sh
make test                           # host tests (g++, -DHOST_TEST, stubs)
make build [version=x.y.z]          # host tests + compile -> dist/garage-<version>.bin
make ota version=x.y.z              # dist/garage-<version>.bin -> .ota (decoded back and checked)
make upload [port=/dev/ttyACM0]     # compile + USB flash (--device): the bench board only
make update ip=<ip> [version=]      # network update, host network (token: $GARAGE_TOKEN or asked)
make smoke ip=<ip>                  # read-only checks against a running board
make shell                          # a shell in the image
```

- Board: Arduino UNO R4 WiFi, core `arduino:renesas_uno` 1.6.0. No extra libraries.
- The scripts (`test/run.sh`, `tools/build.sh`, `tools/update.sh`, `tools/make_ota.py`) run inside the
  image; the Makefile is the host entry point. Build output stays inside the project (`build/`).
- `build/` and `dist/` are git-ignored.

### Devices on the LAN

| Board | Id | Address | Use |
|-------|----|---------|-----|
| Garage (production) | `garage-3562d4` | `http://10.1.3.103/` | Read-only (`GET`). Anything else: ask the user |
| Bench | `garage-33ad84` | `http://10.1.3.114/` (DHCP), `/dev/ttyACM0` | Free: flash, door commands, settings |

`make update` does not work from Claude's sandboxed shell (the board cannot reach the script's
temporary HTTP server: `server_unreachable`). The user runs it with `! make update ip=<ip>`; the
bench board can also be flashed over USB (`make upload`).

The bench board has nothing wired; A0 floats (~200). Jumper tables are in the garage `NEXT_SESSION.md`.

## Sound system (`devices/sound-system`)

Single sketch for an Arduino UNO, no tests or tooling yet.

## Platform (`platform/`)

FastAPI + PostgreSQL + React, from fastapi-react-template (`platform/TEMPLATE.md`). Conventions in the
`platform-*` skills. Everything runs in Docker; run `make` from `platform/`.

```
platform/docker-compose.yml   production: app image + Postgres (deploy, or `make up` to try the image)
platform/Dockerfile           production image (API + built SPA)
platform/dev/                 dev compose (bind mounts, live reload) + Dockerfile.backend/.frontend
platform/e2e/                 production image + Postgres + Mailpit + Playwright, specs
platform/backend/ frontend/   the code
platform/.env(.example)       shared settings (.env is git-ignored); platform/docs/configuration.md
```

First time: `make init` (copies `.env.example` to `.env`, starts the dev stack). Sign in at
http://localhost:15173 with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`; codes arrive in Mailpit at
http://localhost:18025.

| Service | Port | Notes |
|---|---|---|
| `frontend` | 15173 | Vite, proxies `/api` to the backend |
| `backend` | 18000 | uvicorn `--reload`, migrations applied on start; `/api/docs` |
| `db` | 15432 | Postgres 18; `app` (dev) and `app_test` (tests) databases |
| `mailpit` | 18025 (UI), 11025 (SMTP) | every email of the dev stack |

| Target | Does |
|---|---|
| `make help` | list the targets |
| `make dev-up` / `dev-down` / `dev-logs` / `dev-ps` | start (build, wait healthy) / stop / follow logs / list the dev stack |
| `make test-backend` / `coverage-backend` | pytest / with coverage (fails under 95 %) |
| `make lint-backend` / `format-backend` | ruff check + format check / ruff format + safe fixes |
| `make test-frontend` / `lint-frontend` / `format-frontend` / `build-frontend` | vitest with coverage / eslint + prettier check / prettier write / Vite build |
| `make lint-e2e` | Prettier check of `e2e/` |
| `make test` / `lint` / `qa` | all unit tests / all linters / both (what CI checks before e2e) |
| `make e2e` | end-to-end suite against the production image; report in `e2e/artifacts/report` |
| `make db-migrate` / `db-revision m="…"` | apply migrations / autogenerate one (read and fix it before committing) |
| `make lock` | recompile `requirements*.txt` with hashes from the `.in` files |
| `make build` / `up` / `down` / `logs` / `pull` | production image `$DOCKER_IMAGE:local` / the production compose (`APP_TAG=local make up`) |

Test and lint targets `exec` into the dev stack, so it must be up. Dependencies: backend — edit
`backend/requirements*.in`, `make lock`, rebuild the backend; frontend — `npm install <pkg>` inside the
frontend container, then restart it (a running Vite answers 504 "Outdated Optimize Dep" until
restarted); e2e — `e2e/package.json` pins `@playwright/test` to the image in `e2e/Dockerfile`, lockfile
regenerated with `node:26-alpine npm install --package-lock-only`. Database shell:
`docker compose --env-file .env -f dev/docker-compose.yml exec db psql -U app -d app`.

The end-to-end Playwright image copies the specs: rebuild it (`docker compose -f e2e/docker-compose.yml
build`, which `make e2e` does) after changing them.

## CI

- `.github/workflows/ci.yml`: garage host tests + firmware build, on changes to
  `devices/garage-iot-controller/` or the workflow.
- `.github/workflows/platform*.yml` and `.github/dependabot.yml`: the platform (`platform-ci` skill).

```sh
gh pr checks <n> --watch
gh run view <run-id> --log-failed
```
