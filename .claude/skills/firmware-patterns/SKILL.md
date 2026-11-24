---
name: firmware-patterns
description: Conventions for the Arduino device controllers in devices/ (based on the garage controller v2) — structure, robustness, API contract for the platform/Home Assistant, versioning, tests and docs. Use for any change under devices/ or when designing a new device or the platform side of a device API.
---

# Firmware patterns — nexusHome devices

Reference implementation: `devices/garage-iot-controller` (README = usage, NOTES = decisions).

## Structure

```
firmware/   <device>.ino (setup + loop), config.h (pins, timings, FW_VERSION), one .h/.cpp per concern
test/       run.sh + <device>_test.cpp host tests, stubs/, api_smoke.sh
tools/      build.sh, update tooling
README.md   hardware, wiring, behaviour, API, build, tests, layout
NOTES.md    status, decisions with reasons, open items
```

## Robustness

- Safety-relevant logic (inputs, relays, state machines, timers) must not depend on the network:
  `WiFi.begin()` can block the loop for seconds. The garage runs that logic in a 100 Hz timer interrupt.
- Non-blocking everything in the loop; fixed buffers, no `String`, bounded memory.
- Hardware watchdog; report `reset_reason`.
- `millis()` only as differences; 64-bit tick counters where values must not wrap.
- Inputs debounced; contacts wired so a broken wire reads the safe state (active low + pull-up).
- Settings in data flash with a versioned format and migration from older records; values out of
  range are clamped on load, never dropped.
- No compiled-in secrets: WiFi and token come from a setup mode and stored settings.

## API contract (what the platform consumes)

- REST under `/api/v1`, JSON, plain HTTP on the LAN.
- `GET /info`: device id, name, `sw_version`, and the **entities** it exposes with their
  Home Assistant kind (cover, light, binary_sensor, sensor…). The platform builds HA entities from it.
- `GET /state`: complete state plus `rev`, a counter that increases on every change (cheap polling).
- One resource per entity with verb endpoints (`/door/open`, `/light/on?duration=`); commands are
  idempotent (`"result":"noop"`) and return the complete new state.
- Errors: proper status + `{"error":{"code":"<code>","message":"<text>"}}` (e.g. 409 `door_busy`).
- POST requires `Authorization: Bearer <token>` and rejects a foreign `Origin`. GETs are open,
  except `GET /settings`, which needs the token.
- `GET /log`: recent events with uptime timestamps.
- Changing the contract is a platform-visible change: update the device README, bump the version,
  and the platform's simulator/contract tests in the same plan.

## Versions and release

- `FW_VERSION` in `firmware/config.h`, semver. Every release that ships bumps it (patch for fixes,
  minor for features); the commit subject ends with `(x.y.z)`.
- `tools/build.sh` must pass (it runs the host tests) before any upload.
- Every build goes to the **bench board first**. The production board is updated by the user
  (`tools/update.sh`) — there is no rollback, a bad build needs a USB cable at the garage.

## Tests

- Logic compiled for the PC with `-DHOST_TEST` against stubs of the Arduino core; simulated time,
  inputs and flash. New logic comes with host tests.
- Hardware behaviour (relays, sensors, WiFi loss, OTA) is checked on the bench board and recorded
  in NOTES with date and result. Checks on the real installation are listed for the user.

## Docs

- README describes the current behaviour and API exactly; NOTES keeps decisions and why.
- `NEXT_SESSION.md` is the hand-off: update it when a session leaves work in progress.
- Everything in English, including the device's web page.
