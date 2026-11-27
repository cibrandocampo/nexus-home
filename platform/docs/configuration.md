# Configuration and deployment

The app is configured through environment variables, read from `.env` (copy `.env.example`). Both the
production stack (`docker-compose.yml`) and the development stack (`dev/docker-compose.yml`) use it; the
development stack overrides a few values itself (database URL, Mailpit, `SITE_URL`, sign-up on, rate
limits off).

## Deploying

1. Copy `docker-compose.yml` and `.env.example` (as `.env`) to the server, for example a folder on a
   Synology NAS used as a Container Manager project.
2. Fill in `.env`: at least `DOCKER_IMAGE`, `POSTGRES_PASSWORD`, `SECRET_KEY`, `DEVICE_TOKEN_KEY`, `SITE_URL`, the SMTP
   settings, `ADMIN_EMAIL` and `ADMIN_PASSWORD`.
3. Start it: `docker compose up -d` (or create the project in Container Manager). The app migrates the
   database on start and creates the first administrator from `ADMIN_EMAIL`.
4. Point the reverse proxy at `APP_PORT` (see [HTTPS](#https-behind-a-reverse-proxy)).

Updating: change `APP_TAG` if needed, then `docker compose pull && docker compose up -d`.

The app container runs as a non-root user with a read-only filesystem; only the database writes to disk,
in `$DATA_PATH/postgres`.

## Variables

### Project and deployment

| Variable | Default | Purpose |
|---|---|---|
| `PROJECT_NAME` | `nexus` | Compose project name (container and network names). |
| `APP_NAME` | `nexusHome` | Name shown in emails and the API title. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING` or `ERROR`. App messages carry ids, never emails, names, codes or tokens; the access log records client address, method, path (without the query string) and status. |
| `DOCKER_IMAGE` | — (required) | Image repository, e.g. `cibrandocampo/nexus-home`. |
| `APP_TAG` | `stable` | Image tag: `stable`, `latest`, a version (`1.2.0`) or `local` (`make build`). |
| `APP_PORT` | `8000` | Host port the app is published on. |
| `DATA_PATH` | `./data` | Folder for persistent data (`postgres/` inside). |
| `ENV` | `production` | Set by the compose files; production enforces the secret check below and hides the API docs. |
| `APP_VERSION` | `dev` | Set by the image build; reported by `/api/health`. |
| `STATIC_DIR` | `/app/static` | Where the image keeps the built frontend. Not set by hand. |

### Database

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_USER` | `app` | Database user. |
| `POSTGRES_PASSWORD` | — | Database password. Letters and digits only: it goes into the database URL. |
| `POSTGRES_DB` | `app` | Database name. |
| `DATABASE_URL` | built from the three above | Set by `docker-compose.yml` (`postgresql+asyncpg://…@db:5432/…`); set it yourself only to use another PostgreSQL server. |

### Sessions

| Variable | Default | Purpose |
|---|---|---|
| `SECRET_KEY` | `change-me` | Signs access tokens. **Production refuses to start** with the default or a key shorter than 32 bytes. Generate one: `openssl rand -hex 32`. Changing it signs everyone out of their current access token (refresh still works). |
| `ACCESS_TOKEN_MINUTES` | `15` | Lifetime of an access token. |
| `REFRESH_TOKEN_DAYS` | `30` | How long a session lasts without use. |
| `REFRESH_REUSE_GRACE_SECONDS` | `10` | A just-rotated refresh token sent again within this window (two tabs) is refused without ending the session. |
| `BCRYPT_ROUNDS` | `12` | Password hashing cost. |
| `COOKIE_SECURE` | `true` | Refresh cookie only over HTTPS. Set `false` only when the app is served over plain HTTP. |

### Email

| Variable | Default | Purpose |
|---|---|---|
| `SITE_URL` | `http://localhost:15173` | Public address of the app, used in email links. |
| `EMAIL_FROM` | `nexusHome <no-reply@example.com>` | Sender of every email. |
| `SMTP_HOST`, `SMTP_PORT` | `localhost`, `587` | SMTP server. |
| `SMTP_USER`, `SMTP_PASSWORD` | empty | SMTP credentials (empty: no authentication). |
| `SMTP_TLS` | `starttls` | `none`, `starttls` or `ssl`. |
| `SMTP_TIMEOUT_SECONDS` | `10` | Give up on the SMTP server after this long. |
| `EMAIL_BACKEND` | `smtp` | `memory` keeps emails in memory without sending them (tests only). |

### Login

| Variable | Default | Purpose |
|---|---|---|
| `ALLOW_SELF_SIGNUP` | `false` | Anyone can create an account with their email; it starts without permissions until an admin grants access. |
| `OTP_MINUTES` | `10` | Validity of an email code. |
| `OTP_MAX_ATTEMPTS` | `5` | Wrong codes before a code is spent. |
| `LOCKOUT_ATTEMPTS`, `LOCKOUT_MINUTES` | `5`, `15` | Wrong passwords within the window that lock password login for the account. |
| `UNVERIFIED_SIGNUP_DAYS` | `7` | Sign-ups never confirmed with a code are deleted after this. |
| `BLOCK_DISPOSABLE_EMAIL` | `true` | Refuse sign-ups from disposable email domains. |
| `DISPOSABLE_EMAIL_EXTRA_DOMAINS` | empty | Comma-separated domains to block as well. |
| `DISPOSABLE_EMAIL_ALLOW_DOMAINS` | empty | Comma-separated domains to allow although listed. |

### Rate limits and proxies

| Variable | Default | Purpose |
|---|---|---|
| `RATE_LIMIT_ENABLED` | `true` | Per-address and per-account limits on login endpoints (in memory, one process). |
| `TRUSTED_PROXIES` | empty | Comma-separated IPs or CIDRs of reverse proxies whose `X-Forwarded-For` is trusted. |

### First administrator

| Variable | Default | Purpose |
|---|---|---|
| `ADMIN_EMAIL` | empty | With `ADMIN_PASSWORD`, created as a password administrator at start-up when no admin exists. An existing user with this email is never changed. |
| `ADMIN_PASSWORD` | empty | Its first password; it must follow the password rules (10+ characters, not only digits, not the email) or the app refuses to start. Change it after the first login. Both empty: no administrator is created. |

### Devices

| Variable | Default | Purpose |
|---|---|---|
| `DEVICE_TOKEN_KEY` | the development key | Fernet key (url-safe base64 of 32 bytes) that encrypts the device tokens in the database. **Production refuses to start** with the development key or a malformed one. Generate one: `openssl rand -base64 32 \| tr '+/' '-_'`. Back it up with the database: if it is lost or changed, every stored token becomes unreadable and each device answers `device_token_unreadable` until an admin re-enters its token. |
| `DEVICE_TIMEOUT_S` | `3` | Seconds to wait for a board's answer before it counts as unreachable. |
| `SCAN_RANGES` | `10.1.2.0/23` | Default ranges of the discovery scan (admins can edit them before each scan): comma-separated IPv4 CIDRs or addresses, at most 1024 addresses in all (`scan_too_large`). |
| `SCAN_CONCURRENCY` | `64` | Addresses probed at once (1 to 256). Each address gets one probe, so no board ever sees more than one request from the scan. |
| `SCAN_TIMEOUT_S` | `1.5` | Seconds to wait for each address. With the defaults a /24 takes about 8 s and the default /23 about 16 s: most addresses do not answer and wait the full timeout. Each address is probed once: a board busy answering someone else at that moment can be missed; scan again. |
| `POLL_INTERVAL_S` | `2` | Seconds between two `GET /state` reads of each device (0.5 to 60). The device page shows changes within about this time. |
| `POLL_OFFLINE_AFTER` | `3` | Failed reads in a row before a device counts as offline. A failed read is retried after 0.5 s, so with `DEVICE_TIMEOUT_S` 3 a silent board is offline after about 12 s. |
| `POLL_OFFLINE_INTERVAL_S` | `5` | Seconds between reads of an offline device; it is back online on the first answer. |
| `EVENT_RETENTION_DAYS` | `365` | Days the event history is kept; the hourly clean-up deletes older events. |
| `LOG_READ_EVERY_S` | `60` | Each online device's event log is read on every change it reports and at least this often. A board keeps only its last 64 events: more than that between two reads (a burst of commands) loses the oldest, and the platform logs a warning. |

### Device simulators (development only)

Read by `dev/docker-compose.yml` for its two simulated garage boards; production ignores them.

| Variable | Default | Purpose |
|---|---|---|
| `SIM_GARAGE_A_TOKEN` | `sim-garage-a-token` | Access token of `sim-garage-a` (`garage-5e1a0a`). |
| `SIM_GARAGE_B_TOKEN` | `sim-garage-b-token` | Access token of `sim-garage-b` (`garage-5e1a0b`). |
| `SIM_SPEED` | `1` | Simulated seconds per real second (door travel, timers). |

## Reaching the devices

The app talks to the boards over plain HTTP on the LAN (`http://<board>/api/v1/…`): polling every
`POLL_INTERVAL_S`, commands, settings and the discovery scan. With the default bridge network of
`docker-compose.yml` the container reaches the LAN through the host (on a Synology, the NAS's own
network; Container Manager needs no extra setting); nothing else is needed.

- `SCAN_RANGES` must be the LAN where the boards live (for example `10.1.2.0/23`), not the Docker
  network.
- Boards get their address by DHCP: a board registered by IP that moves is followed by the next scan
  (only when its old address no longer answers as that board, so a copied identity never receives the
  token). Reserving their addresses on the router avoids the question.
- The boards accept one connection at a time; the app never sends them two requests at once. Keep
  other heavy pollers off them.
- Firmware updates (phase 3) will need the opposite direction too: the boards download from the app's
  LAN address and port (`DEVICE_BASE_URL`), so that port must be open to them.

## HTTPS behind a reverse proxy

The app speaks plain HTTP on `APP_PORT`; HTTPS is the reverse proxy's job (on Synology: Control Panel →
Login Portal → Advanced → Reverse Proxy, from `https://app.example.com` to `http://localhost:APP_PORT`).

- Keep `COOKIE_SECURE=true`: the browser only sees HTTPS.
- Set `TRUSTED_PROXIES` to the proxy's address as the app sees it (on the same host usually the Docker
  network gateway, e.g. `172.16.0.0/12`). Without it every request seems to come from the proxy and the
  per-address rate limits apply to everyone at once. Only list proxies you control: a trusted proxy can
  claim any client address.
- `SITE_URL` must be the public `https://` address.
- The app sends its own security headers (CSP, `X-Frame-Options`, `Referrer-Policy`,
  `X-Content-Type-Options`); the proxy may add HSTS.

## Backups

All state is in Postgres, except the key that decrypts the device tokens: keep a copy of
`DEVICE_TOKEN_KEY` (from `.env`) with the backups. Without it a restored database works, but each
device must be given its token again (Devices → device → Change address or token).

A consistent dump while the stack runs:

```sh
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > backup-$(date +%F).dump
```

Restore into a fresh database (no data yet for this Postgres version), before the app starts on it:

```sh
docker compose up -d db
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < backup.dump
docker compose up -d
```

On Synology, Hyper Backup of the `DATA_PATH` folder is only consistent with the stack stopped; prefer
scheduled dumps (Task Scheduler running the first command).

## Upgrading PostgreSQL to a new major version

A new major version cannot open an older one's files. The image keeps each major in its own folder
(`$DATA_PATH/postgres/18/docker`), so a new one starts empty next to the old data. Upgrading (say
18 → 19) is a dump and restore:

1. Take a dump as above, then `docker compose down`.
2. Change the `db` image in `docker-compose.yml` (`postgres:19-alpine`).
3. Restore as above: `up -d db`, `pg_restore`, then `up -d`.
4. Once the app works, delete the old major's folder (`$DATA_PATH/postgres/18`).
