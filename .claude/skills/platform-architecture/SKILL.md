---
name: platform-architecture
description: Architecture of the nexusHome platform (`platform/`) (FastAPI + PostgreSQL API, React SPA, one production image) and the checks to run before implementing a feature or fix. Use at the start of any feature or fix, before writing code.
---

# Architecture

Paths are relative to `platform/`; run `make` targets from there.

## The system

```
Browser ── React SPA (frontend/) ──fetch /api──► FastAPI app (backend/app) ──► PostgreSQL
                                                     │
                                                     └─ SMTP (Mailpit in dev/e2e)
```

- **One process, one image.** In production the FastAPI app also serves the built SPA (`app/spa.py`):
  `/api/*` is the API, `/assets/*` the hashed bundle, every other GET falls back to `index.html`.
  In development Vite serves the SPA on :15173 and proxies `/api` to the backend on :18000.
- **One instance.** Rate limits (`core/ratelimit.py`) and the clean-up task (`core/scheduler.py`) live
  in the process. Running several replicas needs a shared store first — raise it with the user.
- **Behind a reverse proxy** for HTTPS (Synology DSM). The app trusts forwarded addresses only from
  `TRUSTED_PROXIES`.

## Backend layout (`backend/app/`)

| Module | Holds |
|---|---|
| `main.py` | `create_app()`: settings check, logging, middleware (errors, security headers), routers, SPA |
| `core/` | cross-cutting: `config` (settings), `db` (engine, sessions, `Base`), `errors` (envelope, `AppError`), `security` (passwords, JWT), `ratelimit`, `scheduler`, `headers`, `logging`, `types` |
| `auth/` | `/api/auth`: login by code or password, refresh/logout, own profile; `sessions` (tokens), `otp`, `deps` (`current_user`, `require_role`), disposable domains |
| `users/` | `models.User`, `/api/users` admin API, `service` (rules shared by endpoints), `bootstrap` (first admin) |
| `emails/` | Jinja2 templates per language (`templates/<name>/<lang>.*`), `sender` |
| `models.py` | imports every model module for Alembic |

A feature is a package like `auth/` or `users/`: `models.py`, `schemas.py` (Pydantic in/out),
`router.py` (HTTP only: parse, call, answer), `service.py` when rules are shared or non-trivial. No
repositories or use-case classes: SQLAlchemy sessions are used directly in services. Add layers only
when a real need appears, and ask first.

## Frontend layout (`frontend/src/`)

| Path | Holds |
|---|---|
| `App.jsx` | routes and their guards (`AnonymousOnly`, `RequireSession`, `RequireRole`); lazy pages |
| `api/` | `client.js` (fetch wrapper, token, refresh), `queryClient.js` (TanStack Query, error toasts) |
| `auth/` | `AuthContext` (session state and actions), `useAuth`, route guards |
| `pages/` | one component per route (`admin/` for admin pages), with their tests |
| `components/` | shell (`AppLayout`, `AuthLayout`, `BottomNav`), menus, brand |
| `i18n/` | `en.json`, `es.json`, `gl.json` (same keys), detection |
| `theme.js`, `styles/base.css` | Mantine theme and the few global rules (see platform-frontend) |

## Auth model (summary — details in the platform-security skill)

Access token (JWT, 15 min) in memory, sent as `Authorization: Bearer`; refresh token (opaque, rotated)
in an HttpOnly SameSite=Strict cookie on `/api/auth`. Roles: `none` (signed up, waiting), `user`,
`admin`, checked with `require_role(...)` on the server and `RequireRole` in the UI (UI checks are
convenience only).

## Before implementing — checklist

- [ ] I know which package the code belongs to; routers only do HTTP, rules live in services.
- [ ] I searched for an existing helper (`core/`, `users/service.py`, `api/client.js`, components).
- [ ] Concurrency: any read-modify-write on a user or token takes the row lock in the existing order
      (user row first, then tokens) — see platform-backend.
- [ ] Every new endpoint has a role check, an error code in the envelope and a test per error.
- [ ] Every new UI string exists in the three languages.
- [ ] Nothing here assumes more than one app instance, or I raised it.
- [ ] No abstraction without a second real use (YAGNI); functions over 30 lines get split.

## Red flags — stop and discuss

Business rules in a router or a React component; a new global state store; a background job outside
`core/scheduler.py`; a second database or cache; storing tokens in `localStorage`; disabling a security
header or CSP rule to make something work.

Document significant decisions in the plan or task file.
