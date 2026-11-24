---
description: Close the cycle — docs updated, commit, push, PR created or updated, CI green
argument-hint: <change description or plan slug (optional)>
---

# Push: $ARGUMENTS

**Goal**: the branch's work is documented, committed, pushed, in a PR, with CI green. The user merges.

## 1 — State

`git status`, `git diff --stat`, `git log main..HEAD --oneline`. Nothing to ship → say so and stop.
On `main` with changes → create the right branch first (`git-conventions`).

If the branch belongs to a plan, read the plan and INDEX.md: every task must be `Completed` with
QA `Approved`. Otherwise finish them (`/dev-3-run`) or tell the user what is missing.

## 2 — Docs

Update what the change made stale, nothing more:

- Device `README.md` (API, behaviour, build), `NOTES.md` (status, decisions), `NEXT_SESSION.md`.
- Root `README.md` (structure, devices, getting started).
- `CLAUDE.md` and `.claude/skills/*` if a convention or workflow changed.
- Plan file: mark it implemented, note deviations from the original design.

## 3 — Verify

Unless every commit was QA-approved and nothing changed since, run the full suites and builds of
the areas touched (`dev-workflow`). Red → fix first.

## 4 — Commit and push

Remaining changes → commit per `git-conventions`. `git push -u origin <branch>`.
Hook or push rejected → fix and make a new commit; never `--force`, never `--amend` a pushed commit.

## 5 — PR

No PR for the branch → `gh pr create --base main` with the body format from `git-conventions`.
PR exists → it updates with the push; refresh its body if the summary changed
(`gh api repos/{owner}/{repo}/pulls/<n> --method PATCH -f body=...`).

## 6 — CI

`gh pr checks <n> --watch`. Failure → `gh run view <id> --log-failed`, diagnose, fix locally,
verify, new commit, push, watch again. Don't hand a red PR to the user.

## 7 — Report (in Spanish)

PR link, CI status, what it contains, and what the user must do: review and merge, plus any
check on real hardware.
