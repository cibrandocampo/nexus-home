---
name: git-conventions
description: Branch, commit and pull request conventions for nexusHome. Use before creating a branch, a commit or a PR, or when writing a PR body.
---

# Git conventions — nexusHome

## Branches

```
feat/<slug>    new feature (one per plan: feat/<plan-slug>)
fix/<slug>     bug fix
chore/<slug>   tooling, CI, refactors, Claude config
docs/<slug>    documentation only
```

Always from an up-to-date `main`: `git fetch && git checkout -b <branch> origin/main`.
Never commit to `main` directly. If you started on `main` by mistake, move the work to a branch.

## Commits

```
<type>(<scope>): <subject>

- What changed and why, grouped by area. Wrap at ~100 columns.

Co-Authored-By / session lines as given by the current attribution instructions
```

- **type**: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `ci`, `build`.
- **scope**: the area — `garage`, `sound`, `platform`, `ha` (Home Assistant integration),
  `ci`, `claude`… Omit it only for repo-wide changes.
- **subject**: imperative, lowercase, no final period. Firmware releases end with the version: `(2.0.5)`.
- **Firmware tags**: a garage release is the tag `garage-v<version>` on the main commit that bumped
  `FW_VERSION` (`git tag garage-v2.0.7 <commit> && git push origin garage-v2.0.7`); the workflow
  publishes it. Platform releases are `platform-v<version>`. Pushing a tag publishes: ask the user first.
- **body**: explains behaviour and reasons, not file lists. Mention what was checked on real hardware.
- English only. Author = the local `git config`; never set another identity.
- One commit per task in a plan. Don't mix unrelated changes in one commit.
- Hook fails → fix and commit again. Never `--amend` a pushed commit; never `push --force`.
  Conflicts with `main` → `git merge origin/main`, resolve, new commit.

## Pull requests

- Base `main`. One PR per plan, one per `/fix` or `/audit`.
- Title: `<type>(<scope>): <subject>`, under 70 characters.
- Claude never merges: the user reviews and merges (squash). After a merge, branches that were
  stacked on the merged one must be rebuilt from `main` (cherry-pick), not merged.
- Body:

```markdown
## Summary

- Most impactful change first: what changed and why, concretely.
- ... (≤ 6 bullets)

## Issues

Closes #<n>   (omit the section if no tracked issue is resolved)

## Notes

> **Note**: non-obvious decision and its reason. (Omit the section if none.)

## Hardware

What was checked on a real board, and what the user still has to check. (Omit if not relevant.)

## Test plan

- [x] Only what actually ran and passed (local or CI).
- [ ] What the reviewer must still do.

<attribution lines as given by the current attribution instructions>
```

- Edit a PR body with `gh api repos/{owner}/{repo}/pulls/<n> --method PATCH -f body=...`
  (`gh pr edit` prints a GraphQL deprecation warning).
