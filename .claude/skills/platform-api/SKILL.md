---
name: platform-api
description: REST conventions of the nexusHome platform API (`platform/`) — routes under /api, the error envelope and codes, pagination, auth headers, validation. Use when adding or reviewing endpoints.
---

# API Design

Paths are relative to `platform/`; run `make` targets from there.

## Routes

- Everything under `/api`; one router per package with its prefix (`/api/auth`, `/api/users`).
- Plural nouns, lowercase with hyphens, **no trailing slash** (`redirect_slashes=False`: `/api/users/`
  is a 404, not a redirect). Actions that are not CRUD are sub-paths: `POST /api/users/{id}/set-password`,
  `POST /api/auth/change-password`.
- Integer ids (`/api/users/{user_id}`, `/api/devices/{id}`): users are an admin-only API, and every `user`
  can list all devices anyway, so enumeration is not a concern. Use opaque ids for a resource someone
  must not be able to enumerate.
- `/api/docs` and `/api/openapi.json` exist outside production only.

## Methods and statuses

| | |
|---|---|
| `GET` list/detail → 200 | `POST` create → 201 (with the resource) |
| `PATCH` partial update → 200 (with the resource) | `DELETE` → 204 |
| action endpoints → 200 with a body, or 204 | |

Errors in use:

| Status | Codes |
|---|---|
| 400 | `invalid_request`, `invalid_credentials`, `weak_password`, `password_required`, `password_not_allowed`, `method_mismatch`, `disposable_email`, `device_token_invalid` (on add), `device_token_required`, `invalid_duration` and the board's other `invalid_*` setting codes, `scan_too_large`, `invalid_scan_ranges` (bad `SCAN_RANGES`) |
| 401 | `unauthorized`, `token_expired`, `refresh_in_progress` (another tab is rotating: retry) |
| 403 | `forbidden`, `account_disabled` |
| 404 | `user_not_found`, `device_not_found`, `entity_not_found`, `command_not_found`, `settings_not_supported`, `device_has_no_token`, `not_found` |
| 405 | `method_not_allowed` (wrong method on an existing route) |
| 409 | `email_taken`, `last_admin`, `cannot_delete_self`, `scan_in_progress`, `device_exists`, `device_offline`, `door_busy` (passed through from the board), `device_mismatch` (another board at that host), `device_token_invalid` (stored token refused by the board), `device_token_unreadable` (`DEVICE_TOKEN_KEY` changed) |
| 422 | `validation_error`, `not_a_device`, `invalid_params` (parameters on a command that takes none) |
| 429 | `rate_limited` (with `Retry-After`), `locked` (password lockout) |
| 500 / 503 | `internal_error` / `database_unavailable` |
| 502 | `device_unreachable` (the board did not answer), `device_error` (it answered an unexpected error), `device_save_failed`, `device_token_unconfirmed`, `device_token_unchanged` |

A Starlette `HTTPException` would map to `bad_request` (400) or the generic `http_error`; no endpoint
raises one — use `AppError`.

## Error envelope (every non-2xx answer)

```json
{"error": {"code": "email_taken", "message": "A user with this email already exists"}}
{"error": {"code": "validation_error", "message": "Invalid request",
           "details": [{"loc": ["body", "email"], "message": "..."}]}}
```

- Raise `AppError(status, code, message)` (`core/errors.py`); never `HTTPException` with a free text.
- `code` is stable `snake_case` and the frontend translates it (`login.errors.*`, `users.errors.*`,
  `profile.password.errors.*`) — add the three translations with every new code.
- `message` is for developers (English); never user data, SQL or tracebacks. Unhandled exceptions
  become `internal_error` with the traceback in the log only.

## Bodies

- Pydantic schemas per package (`schemas.py`): inputs named after the action or resource
  (`UserCreate`, `UserUpdate`, `LoginStart`, `SetPassword`), outputs end in `Out` / `Page` / `Result`
  (`UserOut`, `UserPage`, `LoginResult`).
  Output schemas list fields explicitly — never return a model with `password_hash`.
- Emails are normalised (`normalise_email`) and compared case-insensitively.
- Text inputs carry length limits and refuse NUL (`core/types.py`).
- Datetimes are ISO 8601 UTC. Booleans are booleans. Optional fields are present as `null`.

## Lists and pagination

`GET /api/users?q=&role=&active=&page=1&size=20` →

```json
{"items": [...], "total": 42, "page": 1, "size": 20}
```

`page` ≥ 1, `size` 1–100 (default 20). Filters are query parameters named like the field. Every list
endpoint is paginated.

## Auth

- `Authorization: Bearer <access token>` on every protected call. Routers use the aliases in
  `auth/deps.py`: `CurrentUser` (any active account, role `none` included), `RequireUser`
  (`require_role(Role.user)`: user or admin) and `RequireAdmin` (`require_role(Role.admin)`).
  `require_role` takes one minimum role; admin passes every check.
- Session endpoints use the `refresh_token` cookie (path `/api/auth`) — only `/api/auth/refresh` and
  `/logout` read it.
- 401 means "refresh and retry once" to the client (`api/client.js` does it); 403 is final.

## Checklist for a new endpoint

- [ ] Role dependency; tests for anonymous (401), wrong role (403) and the happy path.
- [ ] Every `AppError` code has a test and a translation.
- [ ] Rate limit if it sends email, checks a secret or is expensive (`core/ratelimit.py`).
- [ ] Locks when it reads then writes shared rows (platform-backend → Concurrency).
- [ ] The frontend client function and its MSW handler in tests.
