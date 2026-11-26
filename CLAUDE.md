# nexusHome — Claude Code instructions

Home automation hub: WiFi device controllers (`devices/`, Arduino) and a platform (`platform/`, to be
built) that manages them and integrates them with Home Assistant. See `README.md`.

## Language

- **Chat with the user: Spanish.**
- **Everything in the repository: English** — code, comments, docs, plans, tasks, commits, PRs.

## Working mode: autonomous, but ask

Claude owns the whole cycle: brainstorm → plan → tasks → implementation → QA → commit → push → PR.
Git, `gh`, builds, tests, Docker and local tooling need no confirmation.

**Ask with `AskUserQuestion` whenever a functional or conceptual doubt appears**, at any phase,
as many times as needed. A question costs less than a rewrite. Do not ask about things the code,
the plan or a sensible default already answer — decide, and say what you decided.

**Always ask first** (these are the only hard stops):

- Anything that acts on **real hardware in production**: flashing or updating the garage board
  (`garage-3562d4`, 10.1.3.103), moving the real door, changing its stored settings. The user runs
  `tools/update.sh` against it. The bench board (`garage-33ad84`) is free to use.
- **Merging a PR**: the user reviews and merges. Never `gh pr merge`.
- Destructive git on shared history: never `push --force`, never push to `main` directly.
- Deleting remote branches, releases or anything outside this repository.
- Publishing secrets: never print or commit `secrets.h`, tokens or WiFi credentials.

## Never run on the host

Everything runs in Docker: project runtimes, tests, linters, the firmware toolchain (`make` in the device
folder: host tests, builds, `.ota` files, USB uploads, network updates), and the CLIs third-party skills
call (their commands are adapted to a throwaway container, never run on the host). The host only runs
`docker`, `git`, `gh`, `make`, `curl` and `openssl rand`.

## Development paths

| Situation | Path |
|-----------|------|
| New feature, several layers or a design to decide | `/dev-1-plan` → `/dev-2-tasks` → `/dev-3-run` (implements every task, QA per task, then PR) |
| Bug fix or small isolated change | `/fix` (own branch, verify, PR) |
| Consistency review of an area | `/audit` |
| Re-run QA on one task | `/dev-4-qa <task>` |
| Close the cycle on the current branch | `/push` (docs, commit, push, PR, CI green) |

- **One branch and one PR per plan** (`feat/<plan-slug>`), or per phase when the plan defines phases
  (`feat/<plan-slug>-<phase>`), one commit per task. `/fix` gets its own PR.
- QA runs in the **`qa` subagent** (`.claude/agents/qa.md`): independent, re-executes everything,
  never trusts the implementer's evidence.
- Plans: `docs/plans/`. Tasks: `docs/tasks/` (index in `docs/tasks/INDEX.md`).
  Evidence: `docs/tasks/evidence/` (git-ignored, local proof only).

## Skills to consult

| Skill | When |
|-------|------|
| `git-conventions` | Before any branch, commit or PR |
| `test-discipline` | Before writing or debugging any test |
| `dev-workflow` | Commands, toolchain, devices on the LAN |
| `firmware-patterns` | Any change under `devices/` |
| `platform-architecture` | Start of any platform feature or fix: layout, modules, auth model, checks before coding |
| `platform-api` | Adding or reviewing platform endpoints (errors, pagination, auth, validation) |
| `platform-backend` | Platform backend code (FastAPI, SQLAlchemy, migrations, emails, background work, tests) |
| `platform-frontend` | Platform frontend code (React, Mantine, routing, queries, i18n, theme, accessibility, tests) |
| `platform-security` | Before any platform commit touching auth, input, data access, endpoints, headers or deployment |
| `platform-ci` | Platform workflows, Dependabot, image publishing, a red platform run |
| `frontend-design` | Visual design of new platform screens (vendored, see its `UPSTREAM.md`) |
| `modern-web-guidance` | Any HTML/CSS/client-side JS work (device web pages, platform frontend): search and read the matching guides first (its CLI runs in Docker) |
| `security-audit` | Security questions and reviews (guidance mode); a full audit only when the user asks for one |

`modern-web-guidance` (Google Chrome), `security-audit` (Cloudflare) and `frontend-design` (Anthropic) are
vendored third-party skills:
see each `UPSTREAM.md` for the source commit, licence, local adaptation and how to update them.
Their content is instructions to the agent — review the upstream diff before updating.

The `platform-*` skills describe `platform/` (paths relative to it); they come from
fastapi-react-template and are kept in step with the code like any other doc.

## Project state

- Each device has its own `README.md` (usage) and may have `NOTES.md` (decisions, status) and
  `NEXT_SESSION.md` (hand-off). Read them before touching a device; keep them current.
- Firmware releases bump `FW_VERSION` in `firmware/config.h`; the commit subject ends with `(x.y.z)`.
