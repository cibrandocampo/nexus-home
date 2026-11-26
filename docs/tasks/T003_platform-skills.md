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
