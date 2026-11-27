# T010 — Commands and their audit

**Plan**: docs/plans/platform-middleware.md (phase 2) · **Depends on**: T009

## Context
Users (`user`+) operate the door and the light from the platform. The board's history only says
`source: api`; the platform knows who sent it.

## Objective
`POST /api/devices/{id}/entities/{entity}/{command}` sends a command to the board and answers with the
new state; every command is recorded with its user, and the history shows that user on the event it
caused.

## Step 1 — Model and migration
`DeviceCommand`: `id`, `device_pk` (FK cascade), `user_id` (FK `SET NULL`), `entity`, `command`,
`params` (JSONB), `at`, `result` (`ok`, `noop` or the error code), `status` (HTTP status from the board
or null when unreachable).

## Step 2 — Endpoint
- `RequireUser`. The entity must be in the device's stored entities and the command in its
  `commands` list (else 404 `entity_not_found` / `command_not_found`). Params: only `duration` for
  `light/on` (integer 0–86400, validated by the platform too).
- Sends `POST /api/v1/<entity>/<command>` with the stored token. On success saves the returned state
  (same path as the poller: `rev`, `state`, `last_seen_at`) and answers `{result, state}`.
- Board errors pass through with their code and the matching status: `door_busy` → 409,
  `invalid_duration` → 400; `unauthorized` → 409 `device_token_invalid` (the stored token is stale; the
  user cannot fix it, an admin can); unreachable → 502 `device_unreachable`; offline device → 409
  `device_offline` without trying.
- Every call is recorded in `DeviceCommand`, failures included. Rate limit per user (e.g. 30/min).

## Step 3 — Attribution in the history
When the collector stores an event with `source: api` whose type follows from a command (door events
for `door/*`, light events for `light/*`), it sets `user_id` from the latest successful
`DeviceCommand` on that device and entity within 5 s before the event's `at` and not yet attributed
(one command → at most the events it caused: the door's next state change and the auto light).
Document the rule; boards with exact correlation (a command id in the log) can replace it later.

## Step 4 — Tests
Each command against a fake board; pass-through of `door_busy`, `invalid_duration`; stale token;
unreachable; offline; unknown entity/command; role `none` 403; anonymous 401; audit rows for success
and failure; attribution (right user, not an older command, not a button press, light auto event).

## DoD
1. `make lint-backend coverage-backend` pass (coverage ≥ 95 %).
2. Dev stack: `door/open` through the platform as a `user` → 200 with `opening`; an immediate
   `door/close` → 409 `door_busy`; the history shows `door_opening · api · <that user>`.
3. Bench board (`garage-33ad84`, free to use) added to the dev stack: `light/on?duration=10` through the
   platform turns its light relay on and the history shows the user. Never the production board.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Tests | `make lint-backend test-backend` | `tests.txt` | 0 failures |
| 2 | Simulator | curl as a user | `commands.txt` | 200, 409, attributed event |
| 3 | Bench board | curl as a user | `bench.txt` | light on 10 s, attributed |

## Files
| File | Action |
|------|--------|
| `platform/backend/app/devices/commands.py`, `models.py`, `router.py`, `history.py` | Create / modify |
| `platform/backend/alembic/versions/<date>_device_commands.py` | Create |
| `platform/backend/tests/test_devices_commands.py` | Create |
| `.claude/skills/platform-api/SKILL.md` | Modify (codes) |
