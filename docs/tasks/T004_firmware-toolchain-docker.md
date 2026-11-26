# T004 — Firmware toolchain in Docker

**Plan**: docs/plans/platform-middleware.md (phase 1) · **Depends on**: T003

## Context
The user decided (2026-11-25) that nothing runs on the host. The garage firmware still needs `g++`,
the `arduino-cli` snap (with a hand-replaced 64-bit `bossac`) and `python3` on the host for tests,
builds, `.ota` files and uploads. Phase 3's release workflow needs the same toolchain in CI.

## Objective
Every firmware command runs in a container built from a pinned image; the host needs only Docker,
`make` and `git`; CI uses the same image; CLAUDE.md drops the host exception.

## Step 1 — Image
`devices/garage-iot-controller/docker/Dockerfile`: Debian slim with `g++`, `python3`, `curl`,
`iproute2`, a pinned `arduino-cli` release (checksum verified) and the `arduino:renesas_uno@1.6.0`
core installed at build time; non-root user; the project bind-mounted at `/work`.

## Step 2 — Entry points
`devices/garage-iot-controller/Makefile` (help target like the platform's):
- `make test` → `test/run.sh`; `make build [version=]` → `tools/build.sh`; `make ota version=` →
  `tools/make_ota.py`.
- `make upload [port=/dev/ttyACM0]` → `arduino-cli upload` with `--device` passed through.
- `make update ip= [version=]` → `tools/update.sh` with `--network host`, `-it` and `GARAGE_TOKEN`
  passed by name (`-e GARAGE_TOKEN`, never on the command line).
- Files the container writes are owned by the host user (`-u $(id -u):$(id -g)`).
The scripts stay runnable inside the image; `tools/build.sh` no longer needs the snap workaround
(`build/release` inside the project can stay).

## Step 3 — CI and docs
- `ci.yml` garage job: builds the image (with the GitHub Actions cache) and runs `make build` in it.
- Garage README "Build and upload", "Firmware update over the network" and "Tests": the make targets.
- `dev-workflow` firmware section and `CLAUDE.md` "Never run on the host": exception removed.

## DoD
1. `make test` passes in the container.
2. `make build` produces `dist/garage-<FW_VERSION>.bin`; its size is within 1 % of the host-built
   `dist/garage-2.0.5.bin` (same sources) — identical bytes is not required (paths differ).
3. `make ota version=<FW_VERSION>` writes the `.ota`; `tools/make_ota.py`'s own check (decode) passes.
4. `make upload` flashes the **bench** board (`garage-33ad84`, `/dev/ttyACM0`) and it answers
   `/api/v1/info` with the built version afterwards. Never the production board.
5. `make update ip=<bench ip>`: **run by the user** (`! make update ip=…`); the sandbox cannot serve
   the file to the board.
6. CI garage job passes on the PR using the image.
7. `grep -n "snap\|bossac\|Runs on the host" .claude CLAUDE.md devices -r` finds nothing current.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Host tests | `make test` | `test.txt` | all pass |
| 2 | Build | `make build`; `stat -c %s` of both bins | `build.txt` | within 1 % |
| 3 | OTA | `make ota` | `ota.txt` | written, check passes |
| 4 | USB upload (bench) | `make upload`; curl `/api/v1/info` | `upload.txt` | version matches |
| 5 | Network update | user runs it | `update.txt` | user reports the result |
| 6 | CI | `gh pr checks` | `ci.txt` | garage job passes |
| 7 | Docs | the grep | `grep.txt` | nothing current |

## Files
| File | Action |
|------|--------|
| `devices/garage-iot-controller/docker/Dockerfile`, `devices/garage-iot-controller/Makefile` | CREATE |
| `devices/garage-iot-controller/tools/build.sh`, `README.md` | MODIFY |
| `.github/workflows/ci.yml`, `.claude/skills/dev-workflow/SKILL.md`, `CLAUDE.md` | MODIFY |

## Implementation notes
- Image `nexus-garage-toolchain` (Debian trixie-slim, `g++` 14, `python3` 3.13, `arduino-cli` 1.6.0 with
  its published SHA-256, core `arduino:renesas_uno@1.6.0` installed at build time under `/opt/arduino`,
  world-writable so the container can run as the host user).
- Makefile targets: `test`, `build`, `ota`, `upload` (checks the port exists, passes it with `--device`
  and its group; `flags=` for the watchdog self-test builds the README describes), `update` (host
  network, `-it`, `GARAGE_TOKEN`/`OTA_PORT` passed by name), `smoke`, `shell`, `help`. `IMAGE_BUILT=1`
  skips the image build (CI builds it with the Actions cache first). Checked with `make -n` and
  `make help` inside the image (no `make` on the host).
- Build (`build.txt`): host tests pass; `tools/build.sh` in the container gives 114 084 bytes for
  `2.0.5` against 114 108 for the host-built `dist/garage-2.0.5.bin` (0.02 %); `.ota` written and
  decoded back by `make_ota.py`.
- DoD 4 and 5 wait for the user: the bench board is not plugged in (`/dev/ttyACM0` absent) and does not
  answer at 10.1.3.114. Run `! make upload` with the board on USB, then `! make update ip=<bench ip>`.
- `grep.txt`: no current mention of the snap, `bossac` or host toolchain.
