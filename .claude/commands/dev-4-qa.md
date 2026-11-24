---
description: Run independent QA on one task with the qa subagent
argument-hint: <task id, e.g. T003>
---

# QA: $ARGUMENTS

`/dev-3-run` already runs QA after each task; use this to re-check a task on demand.

1. Locate `docs/tasks/$ARGUMENTS*.md`. Not found → list `docs/tasks/` and ask.
2. Launch the `qa` subagent (`Agent`, `subagent_type: "qa"`) with the task id. Don't pass it
   conclusions, only the id and the branch name.
3. Report the verdict to the user (in Spanish): result, blockers, `NEEDS USER` items.
4. RETURNED → offer to fix the blockers now (that is `/dev-3-run $ARGUMENTS`).
