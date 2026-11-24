# Platform: device middleware

## Context

nexusHome's WiFi controllers (today the garage board) each run their own web page and REST API
(`/api/v1`). There is no central place to see and operate them, their event log is lost on every
restart, and updating firmware needs `tools/update.sh` on a PC. The platform is that central place:
it finds and registers the devices, keeps their state and history, sends commands, changes their
settings and updates their firmware. Home Assistant integration comes later and must fit on top
without rework.

It is built from the `fastapi-react-template` (see [platform-template.md](platform-template.md)),
which provides login, users, roles, languages, theme, Docker and CI.

## Decisions confirmed with the user

| Topic | Decision | Why |
|-------|----------|-----|
| Stack | From `fastapi-react-template`: FastAPI + PostgreSQL + React | User's choice |
| Location | `platform/` in this repository | Firmware, its API contract and its consumer change together |
| Deployment | One app image + PostgreSQL on the Synology (Container Manager) | Two containers |
| Scope v1 | Registry, state and commands; event history; firmware updates; device settings | User's choice |
| Access | Sign-up only if enabled; new accounts have no permissions. `user`: see devices and send commands. `admin`: also settings, firmware, registry, users | The garage door is a house entrance |
| Registration | Network scan (plus manual add by IP) | User's choice |
| Firmware source | GitHub Releases (built by CI on a tag) + manual upload | User's choice |
| Web access | HTTPS through the Synology (DSM) reverse proxy; devices download firmware over plain HTTP from the app's LAN port | Secure session cookies; the WiFi module only speaks plain HTTP without redirects |
| Device page | Generic entity cards + type-specific details from the driver | Keeps what the garage's own page shows |
| Home Assistant | Not now; design leaves room for it (MQTT discovery or a custom integration, to decide later) | Not a priority |

## Design

```
 browser ──HTTPS/HTTP──▶ app (FastAPI + React) ──HTTP /api/v1──▶ devices (LAN)
                          │   ▲                      ▲
                          │   └── GitHub Releases    └── device downloads .ota from app
                          ▼
                       PostgreSQL            (later: HA adapter on the internal event bus)
```

### Devices and entities

- A device is identified by its `/info` `id` (`garage-3562d4`). Its **type** is the id prefix
  (`garage`), which selects a small driver: settings form, firmware asset name, display hints.
  No firmware change is needed.
- Entities come from `/info` `entities` (`type`, `device_class`, `unit`, `state` path in `/state`,
  `commands`). The platform stores them and renders them generically: cover (open/close/stop),
  light (on with duration/off), binary_sensor, sensor. The same model maps 1:1 to Home Assistant later.
- Stored per device: id, name, type, model, host (IP), access token (encrypted at rest with a key
  from the environment), `sw_version`, `modem_fw`, mode, `reset_reason`, MAC, last state JSON, `rev`,
  online flag, last seen, uptime.

### Discovery

- Admin starts a scan over the configured ranges (`SCAN_RANGES`, e.g. `10.1.2.0/23`; editable in the
  UI before scanning). The app probes `GET http://<ip>/api/v1/info` with a short timeout and bounded
  concurrency, and lists the devices found that are not registered (id, name, model, version, IP).
- Adding one asks for its token, checks it with an authenticated read (`GET /settings`), then saves it.
- Manual add by IP for devices outside the ranges. A registered device whose IP changed is found
  again by id on the next scan and its host is updated.

### State polling

- One async loop per device: `GET /state` every 2 s (configurable). When `rev` changes the state is
  saved and published on an internal event bus. Three failed polls → offline (and back online on the
  next answer). An uptime that goes backwards marks a reboot.
- The browser reads state from the app (TanStack Query, 2 s refetch on device pages). The event bus is
  the hook a Home Assistant adapter or a live push (SSE) can subscribe to later.

### Event history

- On `rev` change (and at least every 60 s) the app reads `GET /log` and stores new entries with an
  absolute time (`poll time − (uptime_s − t)`), de-duplicated per boot. Kept `EVENT_RETENTION_DAYS`
  (default 365).
- Commands sent through the platform are also recorded with the user who sent them, so the history
  shows "Door opening · api · Ana".
- UI: per-device and global history, filters by device, event type and date range.

### Commands

- `POST /api/devices/{id}/entities/{entity}/{command}` (role `user`+) → device API with its token;
  answers with the new state. Device errors pass through with their code (`door_busy` → 409).
- The door commands ask for confirmation in the UI.

### Device page

- Generic cards per entity (cover, light, binary_sensor, sensor) plus device info (version, WiFi
  signal, uptime, online).
- The type driver adds what the device's own page shows. Garage: who moved the door last
  (`last_source`), the failed-close alert, the light level with the day/night icon, time since the
  last door change.

### Settings

- Admin only. The garage driver shows name, open/close times, light time, night level and LED matrix,
  read from `GET /settings` and written with `POST /settings`. Restart button.
- Token rotation: the app generates a new token, sets it on the device and stores it.
- Changing the device's WiFi network is not offered (it can cut the device off; done on its own page).

### Firmware

- **Releases**: a new nexus-home workflow builds on tags `garage-v<version>`: runs the host tests,
  compiles, converts to `.ota` and publishes a GitHub Release with `garage-<version>.ota`,
  `garage-<version>.bin` and `SHA256SUMS`.
- The app checks the repository's releases (public API) every 6 h and on demand, downloads new
  assets for known device types, verifies the checksum and keeps them in its data volume.
- **Manual upload** (admin): a `.ota`, or a `.bin` that the app converts with the same algorithm as
  `tools/make_ota.py` (ported, and verified by decoding its own output). Marked as "uploaded" so a
  bench build is never confused with a release.
- **Update**: admin picks a version for a device → the app serves the file at a plain-HTTP URL on the
  LAN (`DEVICE_BASE_URL`, e.g. `http://10.1.1.20:8000`; no redirects, the module does not follow
  them) → `POST /firmware {url}` → waits for the restart and the new version, as `update.sh` does
  (including checking the version when the request times out). One update at a time per device;
  refused while the door moves (the device answers 409). Each update is recorded (who, from, to,
  result, duration).
- `tools/update.sh` stays for the bench and for when the platform is down.

### Permissions

| Role | Can |
|------|-----|
| none | Log in, see the "waiting for access" page, edit their profile |
| user | See devices, state and history; send commands |
| admin | Everything: scan/add/remove devices, settings, tokens, firmware, users |

### Configuration (new variables)

`DEVICE_TOKEN_KEY` (encryption key), `SCAN_RANGES`, `POLL_INTERVAL_S`, `EVENT_RETENTION_DAYS`,
`DEVICE_BASE_URL`, `GITHUB_REPO` (default `cibrandocampo/nexus-home`), `FIRMWARE_CHECK_HOURS`.

## Scope

### Included
Everything above, a device simulator, docs (platform README, configuration, deployment on Synology),
the firmware release workflow and CI jobs for the platform.

### Not included
Home Assistant integration; live push from the devices (SSE/webhook in the firmware); the WiFi
network change; the sound system (Arduino UNO without WiFi); automations; notifications.

## Affected areas

| Area | Impact |
|------|--------|
| `platform/` | New: app created from the template + device modules |
| `.github/workflows/` | Platform jobs (lint, tests, E2E, image), firmware release on tags |
| `devices/garage-iot-controller` | No firmware change; README points to the platform and the release flow |
| `.claude/` | `platform-patterns` skill (from the template's backend/frontend skills) |
| Root README | Platform section, deployment |

## Implementation order

1. Bring the template into `platform/`, CI jobs, `platform-patterns` skill, Docker Hub name.
2. Device simulator (fake garage implementing `/api/v1` from the README, with doors that move in
   simulated time), used by tests, by the dev compose and by E2E.
3. Device model, token encryption, manual add, roles `user`/`admin` checks.
4. Discovery scan.
5. Polling, online/offline, event bus, state API.
6. Event history (collection, de-duplication, retention, API).
7. Commands and their audit.
8. Settings and token rotation.
9. Firmware: release workflow in nexus-home, GitHub sync, upload + `.bin` → `.ota`, update flow.
10. Frontend: device list, device page (entities, commands, state), history, scan/add, settings,
    firmware pages.
11. E2E against the simulator; deployment docs; checks on the bench board.

## Testing strategy

- Unit and API tests against Postgres with the simulator (and an HTTP mock for error cases:
  timeouts, 401, 409, malformed answers).
- Contract test: the simulator's answers are validated against the JSON shapes documented in the
  garage README, so a firmware API change breaks the build.
- `.bin` → `.ota` converter checked against `tools/make_ota.py` output on the same input.
- E2E: scan finds the simulator, add, open/close, history shows the events, firmware update against
  the simulator.
- Real hardware: the bench board (scan, commands, settings, a real OTA update). The production board
  only for read-only checks; its first update from the platform is done with the user.

## Risks

- **Container networking**: the app must reach the LAN (scan, polling) and the devices must reach the
  app (OTA download). Bridge networking with the port published on the Synology covers both; the
  firewall must allow the devices to the app's port. `DEVICE_BASE_URL` must be the Synology's LAN address and port, not the reverse-proxy HTTPS name.
- **Scanning a /23 network** takes a few seconds; bounded concurrency avoids flooding the WiFi boards.
- **Polling cost**: 2 s per device is fine for a few devices; the event bus allows switching to push later.
- **OTA has no rollback** on the board: updates from the platform are admin-only, and the release
  workflow runs the host tests; bench first remains the rule.
- **Token storage**: losing `DEVICE_TOKEN_KEY` means re-entering every device token (documented, as
  ovh-dyndns does with its key).
