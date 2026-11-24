---
description: Brainstorm and plan a new feature — design, scope and decisions agreed with the user
argument-hint: <brief description of the feature>
---

# Plan feature: $ARGUMENTS

**Goal**: a plan document the user has approved, with no open decisions.
**Behaviour**: think with the user, then write the plan. No code and no tasks yet.

---

## Phase 1 — Context

1. Read `CLAUDE.md`, the memory index, `README.md`, existing `docs/plans/` and `docs/tasks/INDEX.md`.
2. Read the READMEs / NOTES / NEXT_SESSION of every device or module the feature touches.
3. Explore the affected code (directly, or with `Explore` agents for broad sweeps). Read the real
   code before proposing changes to it — e.g. the device API a middleware will consume.
4. If the feature depends on an external system (Home Assistant, MQTT, a library), check its
   current documentation instead of relying on memory.

## Phase 2 — Brainstorm

Share with the user, briefly:

- What you understood the problem to be, and what you found in the code that matters.
- 2–3 viable approaches with their trade-offs, and **your recommendation**.
- The questions only the user can answer.

Then ask with `AskUserQuestion` (several rounds if needed): goals, constraints, preferences, how
it will be deployed and used, what is out of scope. Recommended option first.

**Never assume a functional or conceptual point. Do not write the plan while one is open.**

## Phase 3 — Write the plan

`docs/plans/<feature-slug>.md`:

```markdown
# Feature name

## Context
What problem it solves and why now.

## Decisions confirmed with the user
| Topic | Decision | Why |
|-------|----------|-----|

## Design
Components, data flow, interfaces (APIs, messages, storage), how it is deployed.
A small ASCII diagram if it helps. Concepts, not code.

## Scope
### Included
### Not included

## Affected areas
| Area | Impact |
|------|--------|
| devices/<name> | ... |
| platform/... | ... |
| CI / tooling | ... |

## Implementation order
High-level steps. Foundations (repo layout, tooling, patterns skill, CI) first.

## Testing strategy
What is unit-tested, what is integration-tested, how devices are simulated, what needs the
real hardware (and therefore the user).

## Risks
```

The plan must be self-contained: someone without this conversation must understand it.

## Phase 4 — Approve

Present the plan (summary + path). Iterate until the user approves. Then create the feature branch
from an up-to-date `main` (`git-conventions`) and commit the plan as the branch's first commit
(`docs(<scope>): plan <feature>`). No push needed yet.

Continue straight to `/dev-2-tasks docs/plans/<feature-slug>.md` unless the user wants to stop.
