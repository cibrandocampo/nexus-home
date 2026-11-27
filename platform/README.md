# nexusHome platform

The central place for nexusHome's WiFi controllers: it finds and registers the devices, keeps their
state and history, sends commands, changes their settings and updates their firmware. Home Assistant
integration comes later. Design and roadmap: [docs/plans/platform-middleware.md](../docs/plans/platform-middleware.md).

It is a FastAPI + PostgreSQL API and a React app in one Docker image, with sign-in (emailed code or
password), users and roles (`none` waits for access, `user` sees devices and sends commands, `admin`
manages everything). It started from a template: see [TEMPLATE.md](TEMPLATE.md).

## What it does

- **Dashboard**: every device with its door and light, quick actions (a door command is confirmed
  first), online or offline. A page per device with its sensors and details.
- **History**: the boards' event logs, collected as they happen and kept for a year
  (`EVENT_RETENTION_DAYS`), by day in each user's time zone, with who sent each command; filters by
  device, event and date.
- **Administration** (role `admin`): find the boards with a scan of the LAN or add one by address (a
  new board without an access token gets one), remove them, change their stored settings, restart
  them, show or change their token. Device tokens are stored encrypted (`DEVICE_TOKEN_KEY`).
- Firmware updates from the platform come in phase 3.

Devices are polled every 2 s (`GET /api/v1/state` of each board); the boards' own API is described
in each device's README (`devices/garage-iot-controller/README.md`).

## Development

Everything runs in Docker; the host needs Docker with Compose, `make` and `git`.

```sh
cd platform
make init        # creates .env and starts the dev stack
```

Then open http://localhost:15173 and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`. Emails
land in Mailpit at http://localhost:18025. Two simulated garage boards run in the dev stack
(`simulator/`, see its README); add them from Devices with a scan of the compose network or by name
(`sim-garage-a`, `sim-garage-b`, tokens in `.env`). `make help` lists every target (tests, linters,
end-to-end suite, migrations, production image).

## Deployment

One app container and PostgreSQL, with `docker-compose.yml` and `.env` (Synology Container Manager or
any Docker host). Every variable, HTTPS and backups: [docs/configuration.md](docs/configuration.md).
