# T002 — Platform CI, Dependabot and image publishing

**Plan**: docs/plans/platform-middleware.md (phase 1) · **Depends on**: T001

## Context
The template's workflows assume the app is the repository root and that every release is an app
release. In nexus-home the app lives in `platform/`, and releases are also cut for firmware
(`garage-v…`, phase 3). The platform must be checked on every change to it, and its image published
to `cibrandocampo/nexus-home` only from main and from platform releases.

## Objective
GitHub Actions lint, test, end-to-end test and build the platform when `platform/` (or its workflow)
changes; the image is published as the template does, keyed on `platform-v<version>` releases; the
garage firmware job is unchanged in behaviour.

## Step 1 — `platform.yml`
New `.github/workflows/platform.yml`, adapted from the template's `ci.yml` (`af8fea9`):
- Triggers: `pull_request` and `push` to main with `paths: [platform/**, .github/workflows/platform.yml]`;
  `release: published`, with every job of a release run guarded by
  `startsWith(github.event.release.tag_name, 'platform-v')`.
- Jobs backend / frontend / audit / e2e / image with `working-directory: platform` (and `context:
  platform` for the image build); the "production database starts" step included.
- Version: `git describe --tags --match 'platform-v*' --always`, with the `platform-v` prefix removed.
- Tags (`docker/metadata-action`, `flavor: latest=false`): `latest` on push to main; on a platform
  release `type=match,pattern=platform-v(\d+\.\d+\.\d+.*),group=1` and `stable` unless prerelease.
- Same push gate as the template (`DOCKERHUB_USERNAME`, `DOCKERHUB_TOKEN`, `DOCKER_IMAGE` variable).

## Step 2 — Other workflows
- `platform-weekly-rebuild.yml`: the template's weekly rebuild; the `stable` channel picks the newest
  release whose tag starts with `platform-v` (`gh release list --json tagName,isPrerelease`), skipping
  when there is none.
- `platform-disposable-domains.yml`: the template's weekly list sync, paths under `platform/`.
- `ci.yml` (garage): `actions/checkout@v7`; a `paths` filter (`devices/garage-iot-controller/**`,
  `.github/workflows/ci.yml`) so a platform-only change does not rebuild firmware. Its toolchain moves
  into Docker in T004, not here.

## Step 3 — Dependabot
`.github/dependabot.yml`: the template's entries with directories under `/platform` (pip
`/platform/backend`, npm `/platform/frontend` and `/platform/e2e`, docker and docker-compose
`["/platform", "/platform/dev", "/platform/e2e"]` grouped, ESLint majors held), plus github-actions `/`.

## DoD
1. actionlint (Docker) passes on every workflow.
2. On the PR, the platform jobs run and pass; a commit touching only `devices/` does not start them,
   and one touching only `platform/` does not start the garage job (checked on the PR's runs).
3. The image job builds without pushing on the PR (no push events).
4. Tag logic checked without publishing: `docker/metadata-action` inputs reviewed against a dry run
   of the `type=match` pattern (a shell `sed -E` of `platform-v1.2.0` → `1.2.0`; `garage-v2.0.5` → no
   platform job runs, from the guard).

## Evidence
| # | Check | Command | File | PASS when |
|---|-------|---------|------|-----------|
| 1 | actionlint | `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:latest` | `actionlint.txt` | no output |
| 2 | Path filters | `gh run list --branch feat/platform-base --json workflowName,headSha,conclusion` | `runs.txt` | as stated |
| 3 | Image build | the PR's image job log | `image.txt` | built, `push: false` |
| 4 | Tag logic | the dry run | `tags.txt` | as stated |

## Files
| File | Action |
|------|--------|
| `.github/workflows/platform.yml`, `platform-weekly-rebuild.yml`, `platform-disposable-domains.yml` | CREATE |
| `.github/workflows/ci.yml`, `.github/dependabot.yml` | MODIFY / CREATE |

## Implementation notes
- `platform.yml`: the template's `ci.yml` (`af8fea9`) with `defaults.run.working-directory: platform`,
  `context: platform`, the report path `platform/e2e/artifacts/`, and the same `if:` on every job (on a
  release run, only `platform-v…` tags). `paths` filters do not apply to release events, hence the guard.
- Version: `git describe --tags --match 'platform-v*' --always`, prefix removed (also in the Makefile).
- Tags: `type=match,pattern=platform-v(\d+\.\d+\.\d+.*),group=1`; dry run (`tags.txt`):
  `platform-v1.2.0` → `1.2.0`, `platform-v1.2.0-rc.1` → `1.2.0-rc.1`, `garage-v2.0.5` and `v1.0.0` → none.
- Weekly rebuild: the `stable` channel takes the newest non-draft, non-prerelease `platform-v…` release
  (jq checked on sample data: garage releases ignored); none yet → skip (checked against the repository).
- Disposable domains: the template's workflow with the list under `platform/`, own PR branch.
- DoD 2 adjusted: GitHub evaluates `paths` of a PR on its whole diff, and this PR touches both areas, so
  both workflows run here. The filters are checked by review; the first platform-only or devices-only
  PR after the merge confirms them.
