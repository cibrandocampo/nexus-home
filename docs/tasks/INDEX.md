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
| T007 | Discovery scan | T006 | Completed (DoD 3: bench board unplugged) | Approved |
| T008 | Polling, online/offline, event bus | T006 | Completed | Approved |
| T009 | Event history | T008 | Completed | Approved |
| T010 | Commands and their audit | T009 | Completed (DoD 3: bench board unplugged) | Approved |
| T011 | Device settings, restart and token rotation | T006 | Completed (DoD 3: bench board unplugged) | Approved |
| T012 | Frontend: dashboard and device page | T010 | Completed | Approved |
| T013 | Frontend: event history | T012 | Completed | Approved |
| T014 | Frontend: scan, add, remove and device settings (admin) | T012, T007, T011 | Completed | Approved |
| T015 | End-to-end tests, bench-board checks, docs | T013, T014 | Completed (DoD 3: bench board unplugged) | Approved |

```
T006 ─┬─► T007 ───────────────────────────────┐
      ├─► T008 ──► T009 ──► T010 ──► T012 ─┬──┼─► T014 ──► T015
      └─► T011 ────────────────────────────┼──┘             ▲
                                           └─► T013 ────────┘
```

## Series T016–T022 — Platform, phase 3: firmware
Plan: [docs/plans/platform-middleware.md](../plans/platform-middleware.md) · Branch: `feat/platform-firmware`

| ID | Title | Depends on | Status | QA |
|----|-------|------------|--------|----|
| T016 | Firmware release workflow | — | Completed (DoD 2 after push; DoD 4: user) | — |
| T017 | `.bin` → `.ota` converter in the platform | — | Completed | Approved |
| T018 | Firmware catalogue: GitHub sync and uploads | T017 | Pending | — |
| T019 | Simulator: firmware updates | — | Pending | — |
| T020 | Firmware updates from the platform | T018, T019 | Pending | — |
| T021 | Frontend: firmware | T020 | Pending | — |
| T022 | Firmware end-to-end, deployment docs, a real OTA on the bench board | T016, T021 | Pending | — |

```
T016 ───────────────────────────────────────┐
T017 ──► T018 ─┐                            ▼
T019 ──────────┴─► T020 ──► T021 ──────────► T022
```

Status: `Pending` → `In progress` → `Completed`. QA: `—` → `Approved` / `Returned (B1…)`.
