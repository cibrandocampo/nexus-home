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

## Implementation notes

- `.github/workflows/garage-release.yml`: tag `garage-v*` → version check against `FW_VERSION`, the
  toolchain image (same cache as `ci.yml`), `make build` + `make ota`, `SHA256SUMS` checked with
  `sha256sum --check`, `gh release create` with the three files (`--verify-tag`, `--generate-notes` from
  the previous `garage-v*` tag, `--prerelease` for a suffixed version). `contents: write` on this job
  only.
- Deviation from Step 1 / DoD 2: a `workflow_dispatch` run can only start once the workflow is on the
  default branch, so the dry run of the PR is a `pull_request` trigger limited to this file: it builds
  the files from the branch's `FW_VERSION` and keeps them as an artifact, publishing nothing. A manual
  run (`workflow_dispatch`, version input) does the same after the merge.
- DoD 1: actionlint clean (`actionlint.txt`).
- DoD 3: the Version step's script run on its own (alpine) with no version, the right tag, a wrong tag
  (fails: "version 2.0.7 does not match FW_VERSION 2.0.6") and a pre-release config (`PRERELEASE=true`)
  (`version-check.txt`).
- DoD 2: the PR's run of this workflow (after the push).
- DoD 4: NEEDS USER — the first real release `garage-v2.0.6` (pushing the tag publishes).
- Docs: garage README "Releases", `platform-ci` (the workflow), `git-conventions` (firmware tags, ask
  before pushing one).
- The Platform workflow's `release` trigger already skips non-`platform-v` releases (checked in
  `platform.yml`: every job's `if:`).

## QA — RETURNED (round 1)

**Date**: 2026-11-28

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | actionlint (Docker, `-no-color`) on all workflows | `docs/tasks/evidence/T016/qa/actionlint.txt` | PASS (no findings) |
| 2 | Version step, run verbatim (extracted from the workflow) in alpine: empty (PR), right tag, right input, wrong tag, wrong input, `$(id)` in the tag, `platform-v` tag, pre-release, pre-release mismatch | `docs/tasks/evidence/T016/qa/version-check.txt` | PASS (mismatches exit 1 with the message; `$(id)` not expanded; `PRERELEASE=true` only for a suffix) |
| 3 | The build step as the workflow runs it: `make build` (host tests + compile), `make ota version=2.0.6`, `SHA256SUMS`, `sha256sum --check` | `docs/tasks/evidence/T016/qa/build-ota-sums.txt` | PASS (all tests passed; `garage-2.0.6.ota`/`.bin` OK) |
| 4 | Publish step, run verbatim with a stub `gh` in scratch repos: previous garage tag with a platform tag between, pre-release, first release ever | `docs/tasks/evidence/T016/qa/publish-args.txt` | PASS (`--notes-start-tag` skips the platform tag and is left out with no previous tag; `--prerelease` only for rc) |
| 5 | Platform workflow skips `garage-v` releases; weekly rebuild filters on `platform-v` | `docs/tasks/evidence/T016/qa/platform-guard.txt` | PASS (6 jobs, 6 guards) |
| 6 | Simulator lint + tests (they read the garage README) | `docs/tasks/evidence/T016/qa/simulator-tests.txt` | PASS (109 passed, 99%) |
| 7 | Full platform suites: backend coverage, frontend | `docs/tasks/evidence/T016/qa/platform-tests.txt`, `docs/tasks/evidence/T016/qa/frontend-rerun.txt` | FAIL (backend 628 passed, 100%; frontend 5 then 1 test timed out at 5000 ms) |
| 8 | DoD 2: dry run on GitHub (PR run, artifact with the 3 files) | after the push | PENDING (implementer) |
| 9 | DoD 3 on GitHub (a manual run with a wrong version) | local equivalent in #2; the `workflow_dispatch` only works after the merge | PASS locally; on GitHub after the merge |
| 10 | DoD 4: first real release `garage-v2.0.6` | — | NEEDS USER |

### Blockers
- **B1**: `.github/workflows/garage-release.yml:102-103`. Step 1 says `contents: write` only for the
  release step. What I found: one job holds `contents: write` for the whole run, on every event
  (`pull_request` from a same-repo branch, `workflow_dispatch`, tag push). `actions/checkout@v7` (line 42)
  persists that token in `.git/config` while `make build`/`make ota` run the branch's Makefile and
  scripts on the runner. Expected: split the work into two jobs.
  - A build job with `contents: read` and `persist-credentials: false`. It does the version check,
    build, sums and artifact upload, and runs on every event.
  - A `publish` job with `needs: build`, `if: github.event_name == 'push'` and `contents: write`. It
    downloads the artifact, checks out with `fetch-depth: 0` for the notes, and runs
    `gh release create`. It must not run the Makefile.

  This way a PR or manual run never gets a write token, and code that holds the write token only
  publishes the files. The task's implementation notes say "on this job only" but do not mark this as
  a deviation from Step 1. Evidence: lines 23-24 / 102-103 of the workflow; actionlint cannot flag it.
- **B2**: platform frontend suite is red: `src/pages/ProfilePage.test.jsx` "shows the account and saves
  a new name", "explains a weak_password answer", "explains a boom answer" and
  `src/pages/HistoryPage.test.jsx` "lists the events by day, in the user time zone", "filters by device,
  event and dates, and keeps the filters in the address" hit `TestTimeoutError: Test timed out in 5000ms`
  (`platform-tests.txt`: 5 failed / 208). A rerun still failed 1 ("shows the account and saves a new
  name", `frontend-rerun.txt`). T016 does not touch the frontend, and the host was loaded (load avg
  around 6, other QA runs). The tests still flake under load. Expected: make them fast or deterministic,
  or give them an explicit timeout, then show a clean `make test-frontend` run.

### Observations (non-blocking)
- Version step (line 51) writes `VERSION` to `$GITHUB_ENV` before the check. Tag names cannot hold a
  newline, and a dispatch input needs write access. Still, writing it after the comparison is safer,
  because post-job steps run even when the step fails.
- No check that the tagged commit is on `main` (`git merge-base --is-ancestor "$GITHUB_SHA"
  origin/main`). The docs require it, but nothing enforces it.
- A non-prerelease `garage-v` release becomes the repository's "Latest" release, taking that label from
  `platform-v` ones. Nothing in the repo relies on `/releases/latest` today. Consider `--latest=false`,
  or document it.
- For `2.1.0` after `2.1.0-rc1`, the release notes start at the rc tag, so they only cover the changes
  since the rc.
- Step name "Keep the files (manual runs)" also runs on pull requests.
- The working tree also holds another task's in-progress changes (`platform/simulator/**` and the garage
  README event list `firmware_update_failed`, line 267). When committing T016, stage only the
  "Releases" hunk of the README.

## Fixes after QA round 1

- **B1**: two jobs. `build` (every event, `contents: read`, checkout with `persist-credentials: false`):
  version check, the "tag on main" check (push only), host tests, build, `.ota`, `SHA256SUMS`, artifact.
  `publish` (`needs: build`, only for a pushed tag, `contents: write`): downloads the artifact, checks
  the sums again and runs `gh release create`; it checks out nothing and runs nothing from the branch.
  The previous stable garage release for the notes comes from `gh release list` (the API), so release
  candidates and platform releases are skipped.
- O1: the version reaches `GITHUB_ENV` / outputs only after the check. O2: a tag not on a `main` commit
  fails. O3: `--latest=false` (a firmware release never becomes the repository's "Latest"). O4: notes
  start at the previous stable garage release. O5: the artifact step now runs for every event, by design
  (it is what `publish` uses).
- **B2** (outside T016): `vite.config.js` `testTimeout: 15_000` — page tests render the whole app and
  timed out at 5 s with several suites running at once (the QA's runs and mine shared the machine). A
  real hang still fails. Separate commit.

## QA — APPROVED (round 2)

**Date**: 2026-11-28

| # | Check | Evidence | Result |
|---|-------|----------|--------|
| 1 | B1: two jobs. `build` has `contents: read`, `persist-credentials: false` and runs on every event. `publish` has `needs: build`, `if: push`, `contents: write`, no checkout and no Makefile; it only downloads the artifact, runs `sha256sum --check` and `gh release create` | workflow read (lines 30-120) | PASS |
| 2 | actionlint (Docker, `-no-color`) on all workflows | `docs/tasks/evidence/T016/qa/r2-actionlint.txt` | PASS (exit 0, no findings) |
| 3 | Action versions exist (`download-artifact@v8`, `upload-artifact@v7`; the others as in `ci.yml`/`platform.yml`) | `docs/tasks/evidence/T016/qa/r2-action-versions.txt` | PASS |
| 4 | Version step run verbatim (extracted with yq, `bash -eo pipefail`, git repo with `origin/main`): PR, right tag on main, right tag off main, wrong tag, dispatch right/wrong, `$(id)`, rc, rc mismatch | `docs/tasks/evidence/T016/qa/r2-version-check.txt` | PASS (the off-main tag fails with "release tags go on a commit of main"; on every failure `GITHUB_ENV`/`GITHUB_OUTPUT` stay unwritten (O1); `prerelease=true` only for a suffix) |
| 5 | Publish step run verbatim with a stub `gh` (real jq): previous stable garage release with a platform release in between, rc, first release ever, rerun with the tag already listed; gh 2.97 flags exist | `docs/tasks/evidence/T016/qa/r2-publish-args.txt`, `docs/tasks/evidence/T016/qa/r2-gh-flags.txt` | PASS (`--notes-start-tag garage-v2.0.5`, `--latest=false`, `--verify-tag`, `--prerelease` only for rc, no start tag the first time) |
| 6 | `make build` (host tests + compile), `make ota version=2.0.6`, `SHA256SUMS` + `sha256sum --check` | `docs/tasks/evidence/T016/qa/r2-build-ota-sums.txt` | PASS |
| 7 | B2: `make test-frontend` on a loaded host (load avg 3.7-5.6) | `docs/tasks/evidence/T016/qa/r2-frontend.txt` | PASS (208/208, 0 timeouts) |
| 8 | Backend coverage, frontend lint, simulator tests | `docs/tasks/evidence/T016/qa/r2-backend.txt`, `docs/tasks/evidence/T016/qa/r2-simulator.txt` | PASS (628 passed, 100%; simulator 99%, exit 0) |
| 9 | Platform workflow skips `garage-v` releases | round 1 `platform-guard.txt`; `platform.yml` unchanged | PASS |
| 10 | DoD 2: the PR's run on GitHub (artifact with the 3 files) | after the push | PENDING (implementer, at `/push`) |
| 11 | DoD 3 on GitHub (manual run with a wrong version) | local equivalent in #4; `workflow_dispatch` works only after the merge | PASS locally |
| 12 | DoD 4: first real release `garage-v2.0.6` | — | NEEDS USER |

### Observations (non-blocking)
- `.claude/skills/platform-ci/SKILL.md` still says the notes come "from the commits since the previous
  `garage-v` tag". The workflow now starts them at the previous *stable* garage release. The skill also
  leaves out the main-ancestor check and `--latest=false`. Worth a one-line update.
- A bare tag `garage-v` gives an empty version, which falls back to `FW_VERSION`, so the check passes.
  The publish step then targets `garage-v<FW_VERSION>`, and `--verify-tag` fails unless that tag already
  exists. Unlikely. Refusing an empty version on `push` would close it.
- If `config.h` stops matching the `sed` pattern, a PR run passes the Version step with an empty version
  and only fails later at `make ota` (usage error). It is harmless, but the error message is not clear.
- When committing T016, stage only the README's "Releases" hunk: the `firmware_update_failed` line
  belongs to T019.

## After QA round 2

- `platform-ci` describes the two jobs, the `main` check, `--latest=false` and where the notes start.
- The Version step fails clearly on a `config.h` without `FW_VERSION` and on a bare `garage-v` tag.
