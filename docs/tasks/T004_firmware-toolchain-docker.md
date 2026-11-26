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

## QA — RETURNED (round 1)

**Date**: 2026-11-26

`make` is not installed on this host, so each target's recipe was taken from `make -n` inside the image
and run from the host with the same `docker run` line. The run used a clean `git archive HEAD` copy of
the device folder, so the shipped `dist/garage-2.0.5.bin` was not overwritten.

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 0 | Image builds from scratch (`--no-cache`): arduino-cli 1.6.0 checksum OK, core renesas_uno 1.6.0, g++ 14.2, Python 3.13.5, make 4.4.1 | `docs/tasks/evidence/T004/qa/image-build.txt` | PASS |
| 0b | `make help` and `make -n` for every target; argument guards (`ota`/`update` without args, missing port) exit 2 with usage | `docs/tasks/evidence/T004/qa/make-dryrun.txt` | PASS |
| 1 | `make test` recipe: all tests passed | `docs/tasks/evidence/T004/qa/test.txt` | PASS |
| 2 | `make build` recipe: `dist/garage-2.0.5.bin` 114 084 bytes, against 114 108 for the host-built one (0.021 %). The host-built file still matches, byte for byte, the payload of the Nov 24 `.ota`. CI gives the same 114 084 | `docs/tasks/evidence/T004/qa/build.txt` | PASS |
| 3 | `make ota version=2.0.5` recipe: `.ota` written (84 953 bytes); an independent decode gives back the exact `.bin` (length, CRC and magic OK) | `docs/tasks/evidence/T004/qa/ota.txt` | PASS |
| 4 | USB upload to the bench board | — | NEEDS USER |
| 5 | Network update | `docs/tasks/evidence/T004/qa/it-without-tty.txt` | NEEDS USER (see B1) |
| 6 | CI garage job at f7f9887: image built with the GHA cache (scope `garage-toolchain`), `make build IMAGE_BUILT=1` passed | `docs/tasks/evidence/T004/qa/ci.txt` | PASS |
| 7 | grep: the only hits for snap/bossac are in NOTES.md, marked superseded; the rest are CSS scroll-snap and "snapshot" | `docs/tasks/evidence/T004/qa/grep.txt` | PASS |

### Blockers
- **B1**: `devices/garage-iot-controller/Makefile:38`: `make update` always passes `-it`. Docker refuses
  that when stdin is not a terminal ("cannot attach stdin to a TTY-enabled container because stdin is
  not a terminal", exit 1, `it-without-tty.txt`). The documented way to run DoD 5 is `! make update
  ip=…` (`.claude/skills/dev-workflow/SKILL.md:46`, and this task's notes), and Claude Code's `!`
  commands run without a terminal, so that path fails before `update.sh` starts. Expected: `-i`, plus `-t`
  only when stdin is a terminal (for example `$(shell [ -t 0 ] && echo -t)`), so a set `GARAGE_TOKEN`
  works without a TTY. The token prompt (`stty -echo`) can stay for terminal use. Alternatively, change
  the docs to say a real terminal is required.

### NEEDS USER
- `make` is not installed on the host (`command -v make` → not found). CLAUDE.md, the README and the
  Makefile header all treat `make` as a host tool, so install it (`sudo apt install make`) before DoD 4–5.
- DoD 4: `make upload` with the bench board (`garage-33ad84`) on `/dev/ttyACM0`, then `/api/v1/info`.
- DoD 5: `make update ip=<bench ip>` (after B1, or from a real terminal).

### Observations (non-blocking)
- The Dockerfile has no `USER`, so the image's default user is root. Every Makefile target and CI pass
  `-u <uid>:<gid>`, which meets "non-root user" in practice; the notes could say so.
- `debian:trixie-slim` is not pinned by digest and the apt packages float. The binary is reproducible
  today (QA and CI both give 114 084 bytes), but a base-image refresh can change it.
- `README.md:72` (root) still lists "Arduino IDE or `arduino-cli`" as prerequisites for the device
  controllers. After this task only Docker, `make` and `git` are needed.
- The implementer's `build.txt` shows a `2.0.5-docker-check` build of 114 108 bytes. The 114 084 figure
  in the notes is not in that file; QA reproduced it. `dist/garage-2.0.5.bin` has an mtime of today
  (18:21) but its bytes are unchanged.
- `make upload` passes only `/dev/ttyACM0` (`--device`). If the board re-enumerated under another node
  during upload, the container could not see it. The UNO R4 WiFi's bridge normally keeps the node; DoD 4
  will show whether it does.

## Fixes after QA round 1
- B1: `make update` and `make shell` pass `-t` only when stdin is a terminal (`TTY`); checked with
  `make -n` inside the image without and with a terminal (`-i` vs `-i -t`). Without a terminal the token
  must come from `GARAGE_TOKEN` (dev-workflow says how to run it from the assistant's prompt).
- Observations: Dependabot watches the toolchain's Debian base; the root README prerequisites point to
  the Docker toolchain; the platform's disposable-domain list header names its new workflow.

## QA — APPROVED (round 2)

**Date**: 2026-11-26 · reviewed at 7672470

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| B1 | `Makefile:7` `TTY := $(shell test -t 0 && echo -t)`, and `update`/`shell` use `-i $(TTY)`. `make -n` inside the image without a terminal gives `-i`, and under `script -qc` (a pty) gives `-i -t`. For real: `docker run -i` without a TTY works, and `-i -t` under a pty works | `docs/tasks/evidence/T004/qa/r2-tty.txt` | PASS |
| B1b | Without a terminal and without `GARAGE_TOKEN`, `update.sh` stops at the token prompt (`stty: … Inappropriate ioctl`, exit 1) after building, before any request to the board. The dev-workflow note (`SKILL.md:45-49`) says to pass `GARAGE_TOKEN` in that case (by name, read from a file, never on the command line) | `docs/tasks/evidence/T004/qa/r2-tty.txt` | PASS |
| 6 | actionlint on all workflows: no findings | `docs/tasks/evidence/T004/qa/r2-actionlint.txt` | PASS |
| obs | Dependabot: a new `docker` entry for `/devices/garage-iot-controller/docker`; the YAML parses, there is no ecosystem/directory clash, and the directory holds the tracked Dockerfile | `docs/tasks/evidence/T004/qa/r2-dependabot.txt` | fixed |
| obs | `README.md:72` prerequisites now point to the Docker toolchain; the platform's disposable-domain list header names `platform-disposable-domains.yml` | `docs/tasks/evidence/T003/qa/r2-grep.txt`, commit 7672470 | fixed |
| 1–3, 7 | Round-1 results stand: 7672470 changes only the `update`/`shell` recipes and the help text, and leaves test/build/ota untouched | round 1 files | PASS |
| 4 | USB upload to the bench board | — | NEEDS USER |
| 5 | Network update | — | NEEDS USER |

### NEEDS USER
- `make` is still not installed on the host: install it first. Then DoD 4 (`make upload` on the bench
  board, then `/api/v1/info`) and DoD 5 (`make update ip=<bench ip>` from a terminal, or with
  `GARAGE_TOKEN` set from the prompt).

### Observations (non-blocking)
- Without a terminal and with no token set, the error is the bare `stty` message. A check in
  `update.sh` (`[ -t 0 ] || { echo "set GARAGE_TOKEN" >&2; exit 2; }` before the prompt), placed before
  the build, would fail faster and more clearly.
- Dependabot's docker ecosystem tracks version tags and digests. `debian:trixie-slim` is a codename tag
  without a digest, so the new entry will probably open no PRs until the `FROM` is pinned by digest.
