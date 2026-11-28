# T019 — Simulator: firmware updates

**Plan**: docs/plans/platform-middleware.md (phase 3) · **Depends on**: none

## Context
The simulator answers `POST /firmware` with 501 `not_simulated`. The platform's update flow (T020)
and its end-to-end tests need a board that downloads, checks and "flashes" a file like the real one.

## Objective
The simulator implements `/firmware` as `firmware/fwupdate.cpp` and the garage README describe it.

## Step 1 — Behaviour
`POST /firmware {"url"}` (token): `door_busy` 409 while the door moves; the URL is tried with a HEAD (5 s,
`server_unreachable` 502 when nothing answers, `file_not_found` 502 on a 404); the file is downloaded
(`download_timeout` / `download_failed`), its header checked (magic and CRC as T017's `check_ota`:
`verify_failed`); then the answer `{"result":"flashing","from":"<version>"}`, silence for
`SIM_FLASH_S` (default 20, real seconds), and a restart with `reset_reason` `pin` and the new version.
The version is the file name's (`garage-<version>.ota`): the simulator cannot read the compiled one
(documented). Hooks: `/sim/firmware_fail` makes the next update fail with a given code.

## Step 2 — Contract
The contract test exempts nothing firmware-related any more: every error in the README table is
produced. README of the simulator updated.

## DoD
1. `make lint-simulator test-simulator` pass (coverage at its current level).
2. Dev stack: an update of `sim-garage-a` from a file served in the dev network ends with the new
   version and `reset_reason: pin`.

## Files
| File | Action |
|------|--------|
| `platform/simulator/sim/{device,app,firmware}.py`, `tests/test_firmware.py`, `tests/test_contract.py`, `README.md` | Create / modify |
