---
description: Consistency audit of a code area — findings, agreed fixes, PR
argument-hint: <area, e.g. "garage HTTP API", "platform device drivers">
---

# Audit: $ARGUMENTS

1. **Conventions.** Read `CLAUDE.md`, the memory and the patterns skill for the area. List the conventions
   that apply to `$ARGUMENTS`.
2. **Explore** only the files of that area (`Explore` agents for wide areas).
3. **Findings table**, grouped by severity (Must fix: breaks a convention or a bug; Should fix:
   inconsistent with the rest; Minor):

   | # | File:line | Issue | Convention | Proposed fix |

4. **Agree** with the user which findings to apply (`AskUserQuestion`, multi-select). Issues found
   outside the area are noted, not fixed.
5. **Apply** on `chore/audit-<slug>` (or the current branch if the user prefers), run the area's
   tests and builds, and launch the `qa` subagent on the diff.
6. **Ship** with `/push`. If a convention itself changed, update its skill in the same PR.
