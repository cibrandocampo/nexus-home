---
description: Implement tasks — one task, or every pending task of a plan — with QA per task, then open the PR
argument-hint: <task id (T003) | plan path or slug (runs all its pending tasks)>
---

# Run: $ARGUMENTS

**Goal**: each task implemented, QA-approved by the `qa` subagent and committed; when the plan is
complete, pushed with a PR whose CI is green.

## Ownership

One-person team: there is no "pre-existing error". Anything broken you meet — a failing test, a
build that doesn't compile, a flaky script — is yours to diagnose and fix before going on.

---

## Step 0 — Select

- Task id → that task. Plan → its pending tasks from `docs/tasks/INDEX.md`, in dependency order.
- Make sure you are on the plan's feature branch (`git-conventions`); create it from an up-to-date
  `main` if it doesn't exist.

## Per task

### 1 — Read

The task file in full (a `QA — RETURNED` section means its blockers come first), `CLAUDE.md`, the
memory (known pitfalls), the patterns skill for the area, and every file you will touch.
Dependencies must be done. Set the task to `In progress` in INDEX.md.

### 2 — Implement

- Read before writing; follow existing patterns.
- No TODOs, placeholders, fake mocks or dead code.
- Tests with the code, following `test-discipline`.
- **Doubt about behaviour or design → stop and ask** (`AskUserQuestion`), with your recommendation.
  Don't silently pick an interpretation the task doesn't settle.
- Re-read what you wrote.

### 3 — Verify your own work

Run every DoD command, saving output to `docs/tasks/evidence/<id>/<name>.txt`, and read it back.
Append to the task file:

```markdown
## Execution evidence
**Date**: YYYY-MM-DD
**Files**: `path` — what changed
| # | Check | Evidence | Result |
### Decisions
```

### 4 — QA

Launch the `qa` subagent (`Agent`, `subagent_type: "qa"`) with the task id and a one-line summary
of what changed. Do not pass it your conclusions.

- **APPROVED** → step 5.
- **RETURNED** → fix every blocker, update the evidence, launch QA again. After 3 rounds still
  RETURNED, stop and explain the situation to the user.
- **NEEDS USER** items → list them for the user at the end; they don't block the commit.

### 5 — Commit

Set the task to `Completed` in INDEX.md and commit the task's changes (code, tests, docs, task
file, INDEX) as one commit following `git-conventions`. Push the branch (`git push -u`).

## When the plan is complete

Run `/push` for the branch: docs pass, PR creation, CI watch. Then tell the user: the PR link,
CI status, and anything that needs them (hardware checks, `NEEDS USER` items, decisions taken).

## Rules

- Never commit a task QA hasn't approved.
- Never mark a DoD item done without a real command's output on file.
- Hardware in production: ask first (CLAUDE.md).
- Never merge the PR.
