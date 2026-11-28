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

## Implementation notes

- `platform/backend/app/firmware/ota.py`: `compress` / `decompress` (the tool's LZSS, unchanged), `encode`
  (refuses an empty image; raises if its output does not decode back, which cannot happen),
  `check` (length, CRC-32, magic: `invalid_firmware` 400), `decode` (check, then the image).
- Fixtures in `backend/tests/fixtures/firmware/` (how they were made: `evidence/T017/fixtures.txt`): the
  first 32 KB of the real 2.0.6 build and a synthetic file, with the tool's `.ota` for each.
- Tests: byte equality with the tool for both fixtures, the tool's files decode to their images, edge
  round trips, every refusal (empty, short, length, CRC, magic with a valid CRC, an HTML page), 256 KB
  in 2.4 s.
- Also checked once on the full 2.0.6 build (114084 bytes): the platform's `.ota` is identical to the
  one `make update` wrote (84958 bytes) and decodes back (`evidence/T017/full-build.txt`).

## QA — APPROVED (round 1)

**Date**: 2026-11-28

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | Backend lint and format (`make lint-backend`) | `docs/tasks/evidence/T017/qa/lint-backend.txt` | PASS |
| 2 | Backend suite with coverage (`make coverage-backend`): 626 passed, total 99 %, `ota.py` 99 % (line 117 only) | `docs/tasks/evidence/T017/qa/coverage-backend.txt` | PASS |
| 3 | Tool vs port, run by QA in python:3.14-slim: all 8 `dist/*.bin` builds, both fixtures, 13 edge inputs (1-18 bytes, ring-size periods 2031/2032/2033, 70 KB of 0xff, random, hash collisions) and 40 seeded random inputs: byte-identical in every case, both outputs decode back; header bytes `02104123 0000000000000040` | `docs/tasks/evidence/T017/qa/tool-vs-port.txt` | PASS |
| 4 | Committed fixture `.ota` files equal a fresh run of `make_ota.py` on the committed `.bin` files | `docs/tasks/evidence/T017/qa/tool-vs-port.txt` | PASS |
| 5 | `check` refuses truncated (by 1 byte, to 20, to 8), extended, bit-flipped and zero-length files; accepts a good one | `docs/tasks/evidence/T017/qa/tool-vs-port.txt` | PASS |
| 6 | Other suites: frontend tests, simulator tests, firmware host tests | `docs/tasks/evidence/T017/qa/{test-frontend,test-simulator,firmware-host-tests}.txt` | PASS |
| 7 | Other linters: frontend, simulator, e2e | `docs/tasks/evidence/T017/qa/{lint-frontend,lint-simulator,lint-e2e}.txt` | PASS |

### Observations        (non-blocking)
- The test case labelled "length mismatch" grows the file (last byte replaced by two); a real `.ota`
  cut short is only covered by `b"short"` (under the header). QA checked tail truncation by hand
  (row 5); a parametrized case `good[:-1]` would make the "truncated file refused" item of Step 2 explicit.
- `ota.py:117` (literal flag with fewer than 8 bits left) is unreachable for encoder output (padding
  is zero bits) and only hit by crafted payloads; coverage is above the threshold.
- `devices/garage-iot-controller/dist/garage-2.0.5.ota` does not decode to the current
  `garage-2.0.5.bin` (the `.bin` was rebuilt on Nov 27 after the `.ota` of Nov 24); tool and port agree
  on that `.bin`, so it is a stale local artefact, not a port defect
  (`docs/tasks/evidence/T017/qa/dist-2.0.5-note.txt`). Worth knowing before T018 imports anything from `dist/`.

## After QA round 1

- O1: a file cut short by one byte is among the refused inputs. O2: a test reaches the decoder's
  half-literal stop with a hand-made payload; `ota.py` at 100 %. O3 (a stale `dist/garage-2.0.5.ota`
  on this computer, older than its `.bin`) noted: T018 imports nothing from `dist/`.
