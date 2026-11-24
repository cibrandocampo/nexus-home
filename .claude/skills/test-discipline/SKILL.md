---
name: test-discipline
description: Testing discipline for nexusHome — strict tests, fail hard, diagnose the root cause (test, code or infra) before changing anything, re-run until deterministically green. Use when writing, running or debugging any test (firmware host tests, platform unit/integration tests, device simulators), or when tempted to skip a test or loosen an assertion.
---

# Test discipline — nexusHome

These tests guard things that act on a house: a garage door, lights, the sound system. A test
softened until it passes while the behaviour is wrong is worse than no test.

## Principles

1. **One test = one concept.** Several asserts are fine if they check one behaviour.
2. **Fail hard.** A test that exposes a real bug stays failing until the bug is fixed. No skip,
   no loosened assert, no "known failure" label.
3. **Diagnose before editing.** Read the failure, reproduce it in isolation, then decide.
4. **Fix at the right layer**:
   - **Test**: wrong assumption, stale fixture, bad simulated timing.
   - **Code**: the behaviour is really wrong.
   - **Infra**: toolchain, container, network, stub that doesn't match the real core/library.
5. **Deterministic green.** Three consecutive runs before calling it done. Timing races hide in
   a single pass. Prefer simulated clocks over real sleeps.

## What to test where

- **Firmware logic** (state machines, timers, parsers, settings storage): host tests with
  `-DHOST_TEST` and stubs (`devices/<device>/test/`). Keep logic free of hardware calls so it can
  run on the PC; time is injected, never read from `millis()` inside the logic under test.
- **Hardware-only code** (pins, radio, flash driver, LED matrix): not unit-testable; covered by a
  bench-board check listed in the task (and in the device NOTES), never claimed as tested.
- **Platform**: unit tests for logic, integration tests against simulated devices (a fake device
  that serves the real device API contract), contract tests that the simulated API matches the
  firmware's documented API.
- **Home Assistant integration**: tested against the HA test harness or the protocol it consumes
  (e.g. MQTT discovery payloads), not by hand only.

## When a test fails

1. Read the full output.
2. Run it alone; if intermittent, treat it as a race — don't retry until green.
3. Classify the layer (above) and apply the minimal fix there.
4. Re-run alone, then the full suite, then 3 times in a row.
5. Write the diagnosis in the task's execution evidence. If it could bite again, save it to memory.

## Forbidden

- Skipped or commented tests without an open task id.
- Vague asserts where an exact value is known.
- Raising timeouts to hide a race.
- Swallowing exceptions inside a test.
- Editing an assert to match wrong behaviour.
- "Pre-existing / not my code": the whole suite is your responsibility.
- Shipping with any test failing or skipped.
- Testing destructive behaviour against production hardware.
