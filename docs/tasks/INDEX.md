# Tasks

## Series T001–T005 — Platform, phase 1: base
Plan: [docs/plans/platform-middleware.md](../plans/platform-middleware.md) · Branch: `feat/platform-base`

| ID | Title | Depends on | Status | QA |
|----|-------|------------|--------|----|
| T001 | Template into `platform/` | — | Completed | Approved |
| T002 | Platform CI, Dependabot and image publishing | T001 | Completed | Approved |
| T003 | Platform skills and project docs | T002 | Completed | Approved |
| T004 | Firmware toolchain in Docker | T003 | Completed (DoD 4–5: user, bench board) | Approved |
| T005 | Garage device simulator | T001 | Completed | Approved |

```
T001 ──► T002 ──► T003 ──► T004
  └────► T005
```

Phases 2 (devices) and 3 (firmware) get their series when phase 1 is merged.

Status: `Pending` → `In progress` → `Completed`. QA: `—` → `Approved` / `Returned (B1…)`.
