# Tasks

## Series T001–T005 — Platform, phase 1: base
Plan: [docs/plans/platform-middleware.md](../plans/platform-middleware.md) · Branch: `feat/platform-base`

| ID | Title | Depends on | Status | QA |
|----|-------|------------|--------|----|
| T001 | Template into `platform/` | — | Completed | Approved |
| T002 | Platform CI, Dependabot and image publishing | T001 | Completed | Approved |
| T003 | Platform skills and project docs | T002 | Completed | Approved |
| T004 | Firmware toolchain in Docker | T003 | Completed (DoD 4–5 done on the bench board, 2026-11-27) | Approved |
| T005 | Garage device simulator | T001 | Completed | Approved |

```
T001 ──► T002 ──► T003 ──► T004
  └────► T005
```

## Series T006–T015 — Platform, phase 2: devices
Plan: [docs/plans/platform-middleware.md](../plans/platform-middleware.md) · Branch: `feat/platform-devices`

| ID | Title | Depends on | Status | QA |
|----|-------|------------|--------|----|
| T006 | Device registry, token encryption and the device client | — | Completed | Approved |
| T007 | Discovery scan | T006 | Pending | — |
| T008 | Polling, online/offline, event bus | T006 | Pending | — |
| T009 | Event history | T008 | Pending | — |
| T010 | Commands and their audit | T009 | Pending | — |
| T011 | Device settings, restart and token rotation | T006 | Pending | — |
| T012 | Frontend: dashboard and device page | T010 | Pending | — |
| T013 | Frontend: event history | T012 | Pending | — |
| T014 | Frontend: scan, add, remove and device settings (admin) | T012, T007, T011 | Pending | — |
| T015 | End-to-end tests, bench-board checks, docs | T013, T014 | Pending | — |

```
T006 ─┬─► T007 ───────────────────────────────┐
      ├─► T008 ──► T009 ──► T010 ──► T012 ─┬──┼─► T014 ──► T015
      └─► T011 ────────────────────────────┼──┘             ▲
                                           └─► T013 ────────┘
```

Phase 3 (firmware) gets its series when phase 2 is merged.

Status: `Pending` → `In progress` → `Completed`. QA: `—` → `Approved` / `Returned (B1…)`.
