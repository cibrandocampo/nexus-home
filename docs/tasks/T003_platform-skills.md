# T003 — Platform skills and project docs

**Plan**: docs/plans/platform-middleware.md (phase 1) · **Depends on**: T002

## Context
The template's stack skills describe exactly the code now in `platform/`, but with root-relative
paths and the template's workflow. nexus-home's CLAUDE.md, QA agent and dev-workflow still say the
platform is "to be built" and point to a `platform-patterns` skill that will not exist.

## Objective
An assistant working on `platform/` finds the stack conventions in `.claude/skills/platform-*`, the
commands in `dev-workflow`, and CLAUDE.md / the QA agent route to them.

## Step 1 — Skills
From the template (`af8fea9`) into `.claude/skills/`, renamed and rewritten for `platform/` paths and
the nexus-home workflow (frontmatter `name` and `description` updated):
`architecture` → `platform-architecture`, `api-design` → `platform-api`, `backend-patterns` →
`platform-backend`, `frontend-patterns` → `platform-frontend`, `security` → `platform-security`,
`ci` → `platform-ci` (the workflows of T002: path filters, `platform-v` releases).
Also `frontend-design` (generic, absent here). Keep nexus-home's own `dev-workflow`, `git-conventions`,
`test-discipline`, `modern-web-guidance`, `security-audit`, `firmware-patterns`.

## Step 2 — Project docs
- `dev-workflow`: the Platform section gets the template's dev-workflow content (stack, ports, make
  targets, migrations, e2e) run from `platform/`.
- `CLAUDE.md`: skills table with the `platform-*` skills; "one PR per plan, or per phase when the plan
  defines phases"; the line about `platform-patterns` replaced.
- `.claude/agents/qa.md`: `platform-*` skills for `platform/`.
- Root `README.md`: a Platform section (what it does, `platform/README.md`, deployment pointer).

## DoD
1. `grep -rn "platform-patterns" CLAUDE.md .claude docs/plans` finds nothing outside the plan's
   decision note.
2. Every path a `platform-*` skill names exists: a script lists the backticked paths starting with
   `platform/` or relative paths the skill says are under `platform/`, and `test -e`s each.
3. No skill claims something the code contradicts: the QA agent checks a sample of five concrete
   claims per skill against the code.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Stale references | the grep | `grep.txt` | as stated |
| 2 | Paths exist | the path script | `paths.txt` | all exist |
| 3 | Claims | sampled claims with file:line | `claims.txt` | all hold |

## Files
| File | Action |
|------|--------|
| `.claude/skills/platform-*/SKILL.md`, `.claude/skills/frontend-design/` | CREATE |
| `.claude/skills/dev-workflow/SKILL.md`, `CLAUDE.md`, `.claude/agents/qa.md`, `README.md` | MODIFY |

## Implementation notes
- Skills copied from the template at `af8fea9` and renamed; each says "Paths are relative to
  `platform/`" under its title; cross-references use the new names (`platform-backend → Concurrency`…).
  `platform-frontend` no longer points to the template's T015 evidence (described instead).
- `platform-ci` is rewritten for nexus-home: path filters, the release guard, `platform-v` tags, the
  three platform workflows, Dependabot under `/platform`.
- `frontend-design` vendored as in the template (Anthropic, Apache-2.0); its `UPSTREAM.md` points to
  `platform-frontend`. CLAUDE.md lists it with the other vendored skills.
- `dev-workflow`: the Platform section has the template's layout, services, targets, dependencies and
  the e2e image rebuild note; CI section lists both workflows.
- Paths (`paths.txt`): 81 backticked paths found under `platform/`; the rest are bare file names inside
  a module table (`schemas.py`, `router.py`… all exist under `platform/backend/app/<module>/`), action
  references, a naming pattern (`Name.module.css`) and workflow files under `.github/workflows/`.

## QA — RETURNED (round 1)

**Date**: 2026-11-26

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | `platform-patterns` only in the plan's decision note (`docs/plans/platform-middleware.md:40`); no template skill names left (`backend-patterns`, `api-design`…) | `docs/tasks/evidence/T003/qa/grep.txt` | PASS |
| 2 | Paths: 130 path-like backticked tokens in the `platform-*` skills checked. All exist except `report/index.html` (inside the downloaded Playwright artifact) and `Name.module.css` (a naming pattern), both correct in context. Bare module-table names resolve under `platform/` | `docs/tasks/evidence/T003/qa/paths.txt` | PASS |
| 3 | Claims: 45 sampled (≥ 5 per `platform-*` skill, plus dev-workflow), each with file:line; all hold. Diff against the template's skills: only renames, cross-references and the T015 evidence pointer | `docs/tasks/evidence/T003/qa/claims.txt` | PASS |
| 4 | Project docs: CLAUDE.md skills table, PR-per-phase rule, qa.md routing, dev-workflow Platform/CI sections, README Platform section | `docs/tasks/evidence/T003/qa/grep.txt` | FAIL (B1) |

### Blockers
- **B1**: `CLAUDE.md:3-4`: the overview still calls the platform "(`platform/`, to be built)". The Context
  section of this task names this stale line as one of the things to fix. Expected: the platform
  described as present (as the README now does). Found: the line is unchanged since 75a9d62 (`grep.txt`,
  last block; the phrase wraps across lines 3–4, so a one-line grep misses it).

### Observations (non-blocking)
- `README.md:11` describes the middleware in the present tense ("finds and registers the WiFi devices,
  keeps their state and history, sends commands… updates firmware"), but phase 1 has none of that yet.
  Consider "will" or "phases 2–3". The deployment pointer is only indirect, through `platform/README.md`
  (it has a Deployment section).
- `platform-frontend` keeps the template's task numbers in its headings ("Visual system (T015)",
  "Navigation and app shell (T009)"). In nexus-home those ids belong to other tasks, or will.

## Fixes after QA round 1
- B1: `CLAUDE.md` opening lines describe the platform as built in phases (plan linked), no longer "to be built".
- Observations: the root README's middleware line says what phase 1 delivers and what phases 2–3 add; the
  `platform-frontend` headings keep the template's task ids as the history of where each rule came from.

## QA — APPROVED (round 2)

**Date**: 2026-11-26 · reviewed at 7672470

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| B1 | `CLAUDE.md:3-5` now describes the platform as FastAPI + React, built in phases, and links the plan (the plan's Phase 1–3 headings are at lines 168, 177 and 187). No "to be built", "to be implemented", "when implemented" or "stack to be decided" left in CLAUDE.md, README.md, the agents or dev-workflow, including phrases that wrap across lines | `docs/tasks/evidence/T003/qa/r2-grep.txt` | PASS |
| 1 | `platform-patterns` still appears only in the plan's decision note | `docs/tasks/evidence/T003/qa/r2-grep.txt` | PASS |
| 2–3 | Skills unchanged since round 1 (7672470 touches none of `.claude/skills/platform-*`), so the paths and claims results stand | `paths.txt`, `claims.txt` | PASS |
| obs | `README.md:11` now says phase 1 delivers sign-in, users and roles, and lists what phases 2–3 add (matches the plan) | `docs/tasks/evidence/T003/qa/r2-grep.txt` | fixed |

### Observations (non-blocking)
- The `platform-frontend` headings keep "(T015)" and "(T009)". This is a stated decision (history of
  where each rule came from) and is acceptable. "the template's T015" in line 111 makes the origin
  explicit; the headings do not.
