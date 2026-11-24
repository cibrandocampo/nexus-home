---
description: Split an approved plan into self-contained, verifiable tasks
argument-hint: <path to plan or feature slug>
---

# Create tasks: $ARGUMENTS

**Goal**: task files that `/dev-3-run` can execute one by one without extra context.
**Behaviour**: divide and write task files. No implementation.

---

## Phase 1 — Read

1. The plan (`$ARGUMENTS` as a path, or search `docs/plans/`). No plan → suggest `/dev-1-plan`.
2. `CLAUDE.md`, the memory (known pitfalls), `docs/tasks/INDEX.md` (last used id), and the code each task will touch.

## Phase 2 — Divide

Each task:

- **Self-contained**: executable from its file alone.
- **One session**: finishable in one `/dev-3-run` pass.
- **Verifiable**: a DoD of real commands.
- **Commit-sized**: it becomes one commit on the feature branch, so it should leave the tree working.

Foundations first (layout, tooling, patterns skill, CI jobs), then features, then cross-layer or
end-to-end tests. Don't invent work the plan doesn't ask for; split tasks that are too big, merge
trivial ones.

Show the user the division — table (id, title, depends on, area) and an ASCII dependency graph —
and adjust it if they want. If something in the plan turns out ambiguous while dividing, ask.

## Phase 3 — Write the task files

Ids continue from INDEX.md (`T001` if none). File: `docs/tasks/TXXX_<slug>.md`:

```markdown
# TXXX — Title

**Plan**: docs/plans/<slug>.md · **Depends on**: TXXX | none

## Context
Why this task exists within the feature.

## Objective
What is true when it is done.

## Step 1 — ...
Concrete instructions. Example code only to illustrate a pattern.

## DoD
1. Each item verifiable with a real command — never "works correctly".

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|

## Files
| File | Action |
|------|--------|
```

No TODOs or placeholders. Hardware-only checks that need the user are marked as such in the DoD.

## Phase 4 — Index

Create or extend `docs/tasks/INDEX.md` (keep earlier series):

```markdown
## Series TXXX–TYYY — Feature name
Plan: [docs/plans/<slug>.md](../plans/<slug>.md) · Branch: `feat/<slug>`

| ID | Title | Depends on | Status | QA |
|----|-------|------------|--------|----|
| T001 | ... | — | Pending | — |
```

Status: `Pending` → `In progress` → `Completed`. QA: `—` → `Approved` / `Returned (B1…)`.

Commit the tasks on the feature branch (`docs(<scope>): tasks for <feature>`), then continue with
`/dev-3-run` on the plan unless the user wants to review first.
