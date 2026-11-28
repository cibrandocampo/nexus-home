# T022 — Firmware end-to-end, deployment docs, a real OTA on the bench board

**Plan**: docs/plans/platform-middleware.md (phase 3) · **Depends on**: T016, T021

## Steps
1. E2E: the server's `DEVICE_BASE_URL` points at itself in the e2e network; an admin uploads a test
   build, installs it on the simulator, the dashboard shows the new version; a second install while one
   runs is refused; a downgrade is warned.
2. Deployment on the Synology (`platform/docs/deployment.md` or a section of configuration.md):
   project in Container Manager, the data volumes (Postgres, firmware), `DEVICE_TOKEN_KEY`,
   `DEVICE_BASE_URL` with the NAS's LAN address and published port, the firewall rule for the boards,
   the reverse proxy for HTTPS, first start, backups.
3. Bench board (NEEDS USER: plugged in): add it, install a test build from the platform, check it comes
   back with it, install the previous version back.
4. Docs: platform README, CHANGELOG, garage README (updates from the platform), plan's phase 3.

## DoD
1. `make e2e` twice in a row green; the Platform workflow green on the PR.
2. Bench board flow recorded (NEEDS USER: plug in the board).
