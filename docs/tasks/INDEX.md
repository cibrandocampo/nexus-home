# Tasks

## Series T001–T005 — Platform, phase 1: base
Plan: [docs/plans/platform-middleware.md](../plans/platform-middleware.md) · Branch: `feat/platform-base`

| ID | Title | Depends on | Status | QA |
|----|-------|------------|--------|----|
| T001 | Template into `platform/` | — | Completed | — |
| T002 | Platform CI, Dependabot and image publishing | T001 | Completed | — |
| T003 | Platform skills and project docs | T002 | Completed | — |
| T004 | Firmware toolchain in Docker | T003 | Pending | — |
| T005 | Garage device simulator | T001 | Pending | — |

```
T001 ──► T002 ──► T003 ──► T004
  └────► T005
```

Phases 2 (devices) and 3 (firmware) get their series when phase 1 is merged.

Status: `Pending` → `In progress` → `Completed`. QA: `—` → `Approved` / `Returned (B1…)`.
