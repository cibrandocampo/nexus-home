---
description: Quick fix — focused bug fix or small change on its own branch, verified and sent as a PR
argument-hint: <what to fix>
---

# Fix: $ARGUMENTS

**Goal**: a minimal, verified fix with its own PR. No plan or task files.

1. **Understand.** Read `CLAUDE.md`, the device/module docs and the affected code. Reproduce the
   problem when possible (a failing test is the best reproduction). If the cause or the expected
   behaviour is unclear, ask. If it grows beyond ~3 files or needs design, stop and propose
   `/dev-1-plan`.
2. **Branch** `fix/<slug>` from an up-to-date `main` (unless the user wants it on the current branch).
3. **Fix** with the smallest change that solves it, plus a test that would have caught it.
   Firmware fix that ships → bump `FW_VERSION` (patch).
4. **Verify**: the touched area's tests, the full suites, and the build (`dev-workflow`).
5. **QA**: for anything beyond a trivial change, launch the `qa` subagent with a short description
   of the fix instead of a task id (it reviews `git diff` and re-runs the suites).
6. **Ship**: `/push` (commit, push, PR, CI). Report the PR link and anything the user must check
   on real hardware.
