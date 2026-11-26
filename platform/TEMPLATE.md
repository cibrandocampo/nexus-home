# Where this app comes from

The platform was created from [cibrandocampo/fastapi-react-template](https://github.com/cibrandocampo/fastapi-react-template)
at commit `af8fea9` (2026-11-26). It was copied once and diverges on purpose: there is no link that
pulls template changes in.

## Copied
`backend/`, `frontend/`, `e2e/`, `dev/`, `Dockerfile`, `.dockerignore`, `.gitignore`,
`docker-compose.yml`, `Makefile`, `.env.example`, `docs/configuration.md`. Renamed to nexusHome
(`PROJECT_NAME=nexus`, `APP_NAME`, `app.name`, page title, image `cibrandocampo/nexus-home`);
`CHANGELOG.md` restarted.

## Not copied, and where it lives instead
| Template | Here |
|----------|------|
| `CLAUDE.md`, `MEMORY.md`, `.claude/` | The repository's own; the stack skills are `.claude/skills/platform-*` |
| `.github/` | `.github/workflows/platform*.yml`, `.github/dependabot.yml` (paths under `platform/`) |
| `README.md`, `LICENSE` | `platform/README.md`; the repository's licence |
| `docs/plans`, `docs/tasks`, `docs/screenshots` | The template's history, not this app's |
| `scripts/` (pre-commit hook) | Not used: it assumes the app is the repository root |

## Porting a template fix
Apply the change by hand under `platform/` and name the template commit in the platform commit
message (`port fastapi-react-template <sha>: …`). Update the commit above only when the whole template
up to that commit has been reviewed.
