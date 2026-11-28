# T017 — `.bin` → `.ota` converter in the platform

**Plan**: docs/plans/platform-middleware.md (phase 3) · **Depends on**: none

## Context
Admins may upload a `.bin` (a bench build); the board only downloads `.ota` files. The platform
converts with the same algorithm as `devices/garage-iot-controller/tools/make_ota.py`.

## Objective
`app/firmware/ota.py` turns a `.bin` into the exact `.ota` the tool writes, verifies its own output by
decoding it, and reads the header of an uploaded `.ota` (length, CRC, magic).

## Step 1 — Port
`encode(bin) -> ota` (header: length, CRC-32, magic `0x23411002`, the 8 version bytes, LZSS payload with
the tool's parameters), `decode(ota) -> bin` (independent decoder), `check_ota(ota)` (magic, length,
CRC; raises `invalid_firmware`). `encode` refuses to return a file that does not decode back to its
input. CPU-bound: callers run it in a thread (`asyncio.to_thread`).

## Step 2 — Tests
Fixtures: two `.bin` files (a real build `dist/garage-2.0.6.bin`, and a small synthetic one with long
repeats and incompressible bytes) and the `.ota` files `make_ota.py` writes for them, committed under
`backend/tests/fixtures/firmware/` (generated once in the toolchain image; the command is in the test
file). Tests: byte-for-byte equal to the tool's output; decode round trip; empty input; bad magic, bad
CRC, truncated file refused; a 256 KB input converts in under 10 s.

## DoD
1. `make lint-backend coverage-backend` pass, coverage ≥ 95 %.
2. The equality test passes for both fixtures.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-backend coverage-backend` | `tests.txt` | 0 failures |
| 2 | Fixtures | how they were made | `fixtures.txt` | tool and port agree |

## Files
| File | Action |
|------|--------|
| `platform/backend/app/firmware/{__init__,ota}.py` | Create |
| `platform/backend/tests/test_firmware_ota.py`, `tests/fixtures/firmware/*` | Create |
