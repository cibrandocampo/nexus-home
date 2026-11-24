---
name: dev-workflow
description: Commands, toolchain and environment for nexusHome — building and testing firmware, devices on the LAN, CI, and (once built) the platform's dev environment. Use when building, testing, flashing, debugging the toolchain or running anything in the project.
---

# Dev workflow — nexusHome

## Repository

```
devices/<device>/      one Arduino controller per device (firmware, tests, tools, docs)
platform/              middleware + Home Assistant integration (to be built)
docs/plans/            feature plans          docs/tasks/  task files + INDEX.md
.github/workflows/     CI
```

## Firmware (garage: `devices/garage-iot-controller`)

Runs on the host: `g++` and `arduino-cli` (snap) are installed.

```sh
test/run.sh                         # host tests (g++, -DHOST_TEST, stubs)
tools/build.sh [version]            # host tests + compile -> dist/garage-<version>.bin
tools/update.sh <ip> [version]      # network update (token: $GARAGE_TOKEN)
test/api_smoke.sh <ip> [token]      # read-only checks against a running board
arduino-cli upload --fqbn arduino:renesas_uno:unor4wifi -p /dev/ttyACM0 firmware   # USB (bench)
```

- Board: Arduino UNO R4 WiFi, core `arduino:renesas_uno` 1.6.0. No extra libraries.
- The arduino-cli snap cannot write to `/tmp`: build output goes inside the project (`build/`).
- The snap's `bossac` was replaced with the 64-bit build; a core reinstall may bring the 32-bit
  one back (`libstdc++.so.6` error on upload).
- `build/` and `dist/` are git-ignored.

### Devices on the LAN

| Board | Id | Address | Use |
|-------|----|---------|-----|
| Garage (production) | `garage-3562d4` | `http://10.1.3.103/` | Read-only (`GET`). Anything else: ask the user |
| Bench | `garage-33ad84` | `http://10.1.3.114/` (DHCP), `/dev/ttyACM0` | Free: flash, door commands, settings |

`tools/update.sh` does not work from Claude's sandboxed shell (the board cannot reach the script's
temporary HTTP server: `server_unreachable`). The user runs it with `! tools/update.sh <ip>`;
the bench board can also be flashed over USB.

The bench board has nothing wired; A0 floats (~200). Jumper tables are in the garage `NEXT_SESSION.md`.

## Sound system (`devices/sound-system`)

Single sketch for an Arduino UNO, no tests or tooling yet.

## Platform

Not built yet. Its plan decides the stack and adds here: how to start the dev environment
(Docker Compose expected, never install runtimes on the host if a container can do it), test, lint
and format commands, and how to run the device simulators.

## CI

`.github/workflows/ci.yml` runs on every PR and on pushes to `main`: garage host tests + firmware
build. New stacks add their own jobs in the same workflow.

```sh
gh pr checks <n> --watch
gh run view <run-id> --log-failed
```
