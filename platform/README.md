# nexusHome platform

The central place for nexusHome's WiFi controllers: it finds and registers the devices, keeps their
state and history, sends commands, changes their settings and updates their firmware. Home Assistant
integration comes later. Design and roadmap: [docs/plans/platform-middleware.md](../docs/plans/platform-middleware.md).

It is a FastAPI + PostgreSQL API and a React app in one Docker image, with sign-in (emailed code or
password), users and roles (`none` waits for access, `user` sees devices and sends commands, `admin`
manages everything). It started from a template: see [TEMPLATE.md](TEMPLATE.md).

## Development

Everything runs in Docker; the host needs Docker with Compose, `make` and `git`.

```sh
cd platform
make init        # creates .env and starts the dev stack
```

Then open http://localhost:15173 and sign in with `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`. Emails
land in Mailpit at http://localhost:18025. `make help` lists every target (tests, linters, end-to-end
suite, migrations, production image).

## Deployment

One app container and PostgreSQL, with `docker-compose.yml` and `.env` (Synology Container Manager or
any Docker host). Every variable, HTTPS and backups: [docs/configuration.md](docs/configuration.md).
