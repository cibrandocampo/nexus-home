# T016 — Firmware release workflow

**Plan**: docs/plans/platform-middleware.md (phase 3) · **Depends on**: none

## Context
The platform installs firmware from GitHub Releases of this repository. A release must be built the
same way every time, only from a commit whose firmware passes its tests, with checksums the platform
verifies.

## Objective
Pushing a tag `garage-v<version>` builds and publishes a GitHub Release with `garage-<version>.ota`,
`garage-<version>.bin` and `SHA256SUMS`; a version with a suffix (`2.1.0-rc1`) is a pre-release.

## Step 1 — Workflow (`.github/workflows/garage-release.yml`)
- Trigger: `push` of tags `garage-v*`. Permissions: `contents: write` only for the release step.
- Refuses a tag whose version differs from `FW_VERSION` in `firmware/config.h` (the version the board
  reports must be the release's).
- Builds the toolchain image (as `ci.yml`), runs `make build` (host tests + compile) and `make ota
  version=<version>`, writes `SHA256SUMS` (`sha256sum garage-<v>.ota garage-<v>.bin`).
- Creates the release with `gh release create` (title `Garage <version>`, notes generated from the
  commits since the previous `garage-v*` tag, `--prerelease` when the version contains `-`), uploading
  the three files. A failure leaves no release.
- The Platform workflow does not run for `garage-v*` releases (its `if:` already guards on
  `platform-v`): check it.

## Step 2 — Docs
Garage README: "Releases" (how to cut one: bump `FW_VERSION`, merge, tag `garage-v<version>` on main,
push the tag; pre-releases; what the platform does with them). `platform-ci` skill: the new workflow.
`git-conventions`: firmware tags.

## DoD
1. `actionlint` (in Docker) passes on the new workflow.
2. A dry run on a fork-free branch: the workflow's build steps run in a `workflow_dispatch` test mode
   (input `dry_run: true`, no release) on the PR and produce the three files with valid checksums
   (artifact uploaded).
3. A tag whose version differs from `FW_VERSION` fails at the check (tested in the dry run with a
   wrong `version` input).
4. NEEDS USER: the first real release (tag `garage-v2.0.6` on main after the merge) — creating a
   release is outward-facing; the user decides when.

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | Lint | actionlint in Docker | `actionlint.txt` | no findings |
| 2 | Dry run | `gh workflow run … -f dry_run=true` | `dry-run.txt` | 3 files, sums match |
| 3 | Version check | dry run with a wrong version | `wrong-version.txt` | fails with the message |

## Files
| File | Action |
|------|--------|
| `.github/workflows/garage-release.yml` | Create |
| `devices/garage-iot-controller/README.md`, `.claude/skills/platform-ci/SKILL.md`, `.claude/skills/git-conventions/SKILL.md` | Modify |
