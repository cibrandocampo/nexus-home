---
name: platform-backend
description: Backend conventions of the nexusHome platform (`platform/`) — FastAPI + SQLAlchemy async + PostgreSQL modules, settings, sessions and locking, migrations, emails, background work, rate limits, tests. Use when writing or reviewing backend code.
---

# Backend Patterns

Paths are relative to `platform/`; run `make` targets from there.

## Stack

Python 3.14 · FastAPI · SQLAlchemy 2 (async, asyncpg) · PostgreSQL 18 · Alembic · Pydantic v2 +
pydantic-settings · PyJWT · bcrypt · aiosmtplib + Jinja2 · pytest (+ pytest-asyncio, httpx) · ruff.
Dependencies are pinned with hashes: edit `requirements.in` / `requirements-dev.in`, then `make lock`.

## Modules

See the platform-architecture skill for the layout. Conventions:

- Routers parse input, call a service or a few queries, return a schema. Rules shared by two endpoints
  go to `service.py`.
- Dependencies are `Annotated` aliases (`Db = Annotated[AsyncSession, Depends(get_session)]`).
- Blocking work never runs on the event loop: bcrypt goes through `hash_password_async` /
  `verify_password_async` (thread).

## Settings

`core/config.py` `Settings` (pydantic-settings) read from the environment; `get_settings()` is cached.
A new setting needs: a typed field with a safe default, a line in `.env.example`, a row in
`docs/configuration.md`, and a check in `production_problems()` if a default is unsafe in production.
Tests override with environment variables + `get_settings.cache_clear()`.

## Database

- Models subclass `core.db.Base`; register new model modules in `app/models.py`.
- Timestamps are timezone-aware UTC (`DateTime(timezone=True)`, `datetime.now(UTC)`).
- Case-insensitive uniqueness through functional indexes (`func.lower(User.email)` — the column, not a
  string literal).
- Migrations: `make db-revision m="what changed"` (autogenerate), then read and fix the file; the name
  prefix is the date. Every migration has a working `downgrade`. The tests run downgrade-to-base and
  upgrade-to-head once per session.

## Concurrency (read this before touching users or tokens)

Requests run concurrently; every read-modify-write takes row locks, always in the same order:

1. the user row (`sessions.lock_user` → `SELECT … FOR NO KEY UPDATE`), then
2. that user's refresh tokens.

Refresh locks the owner's user row `FOR SHARE` (`lock_user(..., share=True)`), then claims the token
with one atomic `UPDATE … RETURNING` (a second claimant gets nothing and falls into the reuse rules). The clean-up task uses
`SKIP LOCKED` and `lock_timeout` 200 ms so it never blocks requests. Guards that count rows ("last
admin") count under the lock. A new rule of this kind needs a concurrency test (see
`tests/test_auth_concurrency.py`).

## Sessions and tokens

`auth/sessions.py` is the only place that creates, rotates or revokes sessions: access JWT (HS256,
`SECRET_KEY`, `ACCESS_TOKEN_MINUTES`), refresh token random and stored as SHA-256, one family per login,
reuse after the grace window revokes the family. Password changes and admin "set password" revoke
every session of the user. One-time codes: 6 digits, stored hashed, `OTP_MINUTES`, `OTP_MAX_ATTEMPTS`.

## Emails

`emails/sender.send_email(to, template, lang, context)`; templates in
`emails/templates/<template>/<lang>.{subject.txt,body.txt,body.html}` for en/es/gl — add all nine
files for a new template. `EMAIL_BACKEND=memory` keeps them in `sender.outbox` (tests). Never log the
address or the body.

## Background work

Two loops, both started in the lifespan:

- `core/scheduler.py`: the hourly clean-up. Periodic tasks there must be idempotent, short, and skip
  locked rows.
- `devices/poller.py`: device polling (user decision 2026-11-27, the one exception). A supervisor keeps
  one task per registered device (`notify()` after an add or remove, a resync every 30 s); each task
  reads `GET /state` through the device client (per-host lock), saves on a new `rev`, tracks
  online/offline and restarts, and publishes on `devices/bus.py` (in-process; slow subscribers lose
  their oldest events). A device task never kills the supervisor; an unexpected error is logged and
  the task resumes after a pause. Tests drive `DevicePoller.poll_once` directly; the ASGI test client
  does not run the lifespan.

Anything else needs a queue — ask first.

## Rate limits and client IP

`core/ratelimit.py`: `RateLimit(name, max, window_s)` sliding windows in memory, keyed by client IP
(`client_ip(request)`, which honours `X-Forwarded-For` only from `TRUSTED_PROXIES`) or by account.
Add new limits to `ALL` so tests reset them. `RATE_LIMIT_ENABLED=false` in dev and e2e.

## Errors and logging

`AppError` for every expected failure (platform-api). Unexpected exceptions are answered by
`UnhandledErrorMiddleware`. Loggers are `logging.getLogger(__name__)` under `app.*`; log ids, never
emails, names, codes or tokens.

## Tests (`backend/tests/`)

- Real PostgreSQL (`app_test` database in the dev stack), migrated once, tables truncated after each
  test; `NullPool`. No SQLite, no mocks of the database.
- Fixtures in `conftest.py` / `helpers.py`: `client` (httpx ASGI), `db`, user factories, login helpers.
- One concept per test; every error code and role check tested; concurrency rules tested with real
  parallel sessions.
- `make coverage-backend` fails under 95 % (currently 100 %).
