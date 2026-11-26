# Every project command runs in Docker (CLAUDE.md: never run on the host). Run from platform/.
DC      := docker compose --env-file .env -f dev/docker-compose.yml
BACKEND := $(DC) exec -T backend
FRONTEND := $(DC) exec -T frontend
# Simulator tests: its code bind-mounted, and the garage README and firmware (its contract) read-only.
SIM     := $(DC) run --rm --no-deps -u $(HOST_UID):$(HOST_GID) -v "$(CURDIR)/simulator:/sim" \
           -v "$(CURDIR)/../devices/garage-iot-controller:/contract:ro" sim-garage-a
PY_IMG  := python:3.14-slim
# Production stack (docker-compose.yml) and the image `make build` produces.
PROD    := docker compose --env-file .env -f docker-compose.yml
E2E     := docker compose -f e2e/docker-compose.yml
IMAGE   ?= $(shell sed -n 's/^DOCKER_IMAGE=//p' .env 2>/dev/null)
# Platform releases are tagged platform-vX.Y.Z (firmware ones garage-v…); the image version drops the prefix.
VERSION ?= $(shell git describe --tags --match 'platform-v*' --always --dirty 2>/dev/null | sed 's/^platform-v//' || echo dev)
export HOST_UID := $(shell id -u)
export HOST_GID := $(shell id -g)

.PHONY: help init dev-up dev-down dev-logs dev-ps lock db-migrate db-revision \
        test-backend coverage-backend lint-backend format-backend \
        test-frontend lint-frontend format-frontend build-frontend \
        test-simulator lint-simulator format-simulator test lint \
        build up down logs pull qa e2e lint-e2e

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-18s %s\n", $$1, $$2}'

init: ## First setup: create .env from the example and start the dev stack
	@test -f .env || cp .env.example .env
	$(MAKE) dev-up

dev-up: ## Start the dev stack (builds images if needed) and wait until healthy
	$(DC) up -d --build --wait

dev-down: ## Stop the dev stack
	$(DC) down

dev-logs: ## Follow the dev stack logs
	$(DC) logs -f

dev-ps: ## Show the dev services
	$(DC) ps

lock: ## Recompile backend and simulator requirements with hashes
	docker run --rm -v "$(CURDIR)/backend:/app" -w /app $(PY_IMG) sh -c "\
	  pip install -q --root-user-action=ignore pip-tools && \
	  pip-compile -q --generate-hashes --strip-extras --allow-unsafe -o requirements.txt requirements.in && \
	  pip-compile -q --generate-hashes --strip-extras --allow-unsafe -o requirements-dev.txt requirements-dev.in && \
	  chown $(HOST_UID):$(HOST_GID) requirements.txt requirements-dev.txt"
	docker run --rm -v "$(CURDIR)/simulator:/app" -w /app $(PY_IMG) sh -c "\
	  pip install -q --root-user-action=ignore pip-tools && \
	  pip-compile -q --generate-hashes --strip-extras --allow-unsafe -o requirements.txt requirements.in && \
	  chown $(HOST_UID):$(HOST_GID) requirements.txt"

db-migrate: ## Apply migrations to the dev database
	$(BACKEND) alembic upgrade head

db-revision: ## Create a migration from the models: make db-revision m="add users"
	$(BACKEND) alembic revision --autogenerate -m "$(m)"

test-backend: ## Backend tests
	$(BACKEND) pytest -q

coverage-backend: ## Backend tests with coverage (fails under the threshold)
	$(BACKEND) sh -c "coverage run -m pytest -q && coverage report"

lint-backend: ## Backend lint and format check
	$(BACKEND) sh -c "ruff check . && ruff format --check ."

format-backend: ## Format the backend and apply safe lint fixes
	$(BACKEND) sh -c "ruff format . && ruff check --fix ."

test-frontend: ## Frontend tests with coverage (fails under the thresholds)
	$(FRONTEND) npm run test:coverage

lint-frontend: ## Frontend lint and format check
	$(FRONTEND) sh -c "npm run lint && npm run format:check"

format-frontend: ## Format the frontend
	$(FRONTEND) npm run format

build-frontend: ## Production build of the frontend (checks it compiles)
	$(FRONTEND) npm run build

test-simulator: ## Simulator tests with coverage, contract included (fails under the threshold)
	$(SIM) sh -c "coverage run -m pytest -q && coverage report"

lint-simulator: ## Simulator lint and format check
	$(SIM) sh -c "ruff check . && ruff format --check ."

format-simulator: ## Format the simulator and apply safe lint fixes
	$(SIM) sh -c "ruff format . && ruff check --fix ."

test: coverage-backend test-frontend test-simulator ## All unit tests

lint-e2e: ## Format check of the end-to-end specs (frontend Prettier config)
	docker run --rm -u $(HOST_UID):$(HOST_GID) -e HOME=/tmp -e NPM_CONFIG_UPDATE_NOTIFIER=false \
	  -v "$(CURDIR):/repo" -w /repo node:26-alpine \
	  npx -y prettier@3.10.1 --config frontend/.prettierrc.json --check 'e2e/**/*.{js,json}' '!e2e/package-lock.json'

lint: lint-backend lint-frontend lint-simulator lint-e2e ## All linters

qa: lint test ## Everything CI checks: linters and unit tests

e2e: ## End-to-end tests: production image + Postgres + Mailpit + Playwright; report in e2e/artifacts/report
	mkdir -p e2e/artifacts
	$(E2E) build
	@# Tear down even when interrupted (Ctrl-C) or failing; keep the runner's exit status.
	trap '$(E2E) down -v --remove-orphans' EXIT INT TERM; $(E2E) run --rm playwright

# --- Production image and stack -----------------------------------------------------------

build: ## Build the production image as $(DOCKER_IMAGE):local
	@test -n "$(IMAGE)" || { echo "Set DOCKER_IMAGE in .env"; exit 1; }
	docker build --build-arg APP_VERSION=$(VERSION) -t $(IMAGE):local .

up: ## Start the production stack (APP_TAG=local runs the image from `make build`)
	$(PROD) up -d --wait

down: ## Stop the production stack
	$(PROD) down

logs: ## Follow the production stack logs
	$(PROD) logs -f

pull: ## Pull the production images (APP_TAG from .env)
	$(PROD) pull

