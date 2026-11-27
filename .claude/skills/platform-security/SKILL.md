---
name: platform-security
description: Security model of the nexusHome platform (`platform/`) (sessions, cookies, roles, rate limits, headers, secrets, logs) and the checklist to run before committing. Use before any commit that touches auth, user input, data access, endpoints, dependencies, headers or deployment. For a full audit use the security-audit skill.
---

# Security

Paths are relative to `platform/`; run `make` targets from there.

## The model — keep it intact

| Area | What is in place | Where |
|---|---|---|
| Access token | JWT HS256, 15 min, **memory only** in the SPA, `Authorization: Bearer` | `core/security.py`, `api/client.js` |
| Refresh token | 256-bit random, stored SHA-256, rotated on every use, family revoked on reuse (10 s grace for parallel tabs); cookie `HttpOnly; SameSite=Strict; Path=/api/auth` (+ `Secure`) | `auth/sessions.py` |
| CSRF | Not needed: state-changing API calls need the Bearer header; the cookie is SameSite=Strict and only read by refresh/logout | — |
| Login | Email code (6 digits, hashed, 10 min, 5 attempts) or password (bcrypt 12); lockout 5 failures / 15 min under a row lock. With sign-up off, the email step says when no account exists (`user_not_found`) — an accepted usability trade-off, limited by the per-IP rate limit | `auth/router.py`, `auth/otp.py` |
| Cookie `Secure` | Follows `COOKIE_SECURE` (true by default; false only for plain-HTTP setups such as e2e) | `auth/sessions.py` |
| Sign-up | Only with `ALLOW_SELF_SIGNUP`; new accounts have role `none`; disposable domains blocked; unconfirmed sign-ups deleted after 7 days | `auth/`, `core/scheduler.py` |
| Roles | `none` < `user` < `admin`, checked server-side on every route (`require_role`); last active admin protected | `auth/deps.py`, `users/service.py` |
| Rate limits | Per IP: login start (10/h), code/password check (10/min), refresh (30/min). Per account: code emails (3/h), password change (5/h), device add or host change (20/h), scan (30/h), device commands (30/min), device token rotate, reveal or re-enter (20/h) | `core/ratelimit.py` |
| Client IP | `X-Forwarded-For` only from `TRUSTED_PROXIES`; uvicorn runs with `--no-proxy-headers` | `core/ratelimit.py`, `backend/entrypoint.sh` |
| Headers | CSP (`script-src 'self'`, no inline scripts; `style-src 'unsafe-inline'` for Mantine), `frame-ancestors 'none'`, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy`, `COOP`; HSTS is the proxy's job | `core/headers.py` |
| Errors | Envelope only; unhandled errors → `internal_error`, traceback in the log | `core/errors.py` |
| Logs | Ids only; no emails, names, codes, tokens; access log without query strings. A 500's traceback ends with the exception message, so exceptions raised on purpose never carry user input | `core/logging.py`, `core/errors.py` |
| Secrets | `SECRET_KEY` default or < 32 bytes refused in production; `.env` git-ignored | `core/config.py`, `app/preflight.py` |
| Static files | Only direct children of the build dir; NUL and traversal refused | `app/spa.py` |
| Container | Non-root (uid 10001), read-only root fs, no capabilities, `no-new-privileges` | `Dockerfile`, `docker-compose.yml` |

## Checklist for every change

### Secrets
- [ ] No secret in code, tests, fixtures, commits, logs or task evidence. Test values are obviously fake.
- [ ] New secrets come from settings, documented in `.env.example` (placeholder) and `docs/configuration.md`.

### Input
- [ ] Every input has a type, length limit and format (Pydantic; `core/types.py`); NUL refused in text.
- [ ] No raw SQL built from input; SQLAlchemy expressions or bound parameters only.
- [ ] No user-controlled path, URL or template name reaches the filesystem, network or Jinja.

### Access
- [ ] Every new route has `current_user` or `require_role(...)`; tests for 401 and 403.
- [ ] Admin actions that could lock everyone out keep the last-admin guard.
- [ ] Rules that read then write run under the row locks (platform-backend → Concurrency).
- [ ] Endpoints that send email, check a secret or are expensive have a rate limit.

### Data exposure
- [ ] Output schemas list their fields; no hashes, tokens or internal flags.
- [ ] Error messages reveal nothing about other accounts beyond what the flow requires.
- [ ] Logs: ids, never personal data or secrets.

### Frontend
- [ ] No token or personal data in `localStorage`/`sessionStorage` (only UI preferences).
- [ ] No `dangerouslySetInnerHTML`, no inline `<script>`, nothing that needs a CSP exception.
- [ ] External links use `rel="noopener noreferrer"`.

### Dependencies and deployment
- [ ] New dependencies are necessary, maintained and pinned (`make lock` / lockfiles).
- [ ] Container hardening, CSP and headers unchanged unless the change is the point — then justified.

## How to apply

Read `git diff` line by line against the checklist. If something is uncertain, ask before committing.
Accepted risks are written next to the code and in the task file.
