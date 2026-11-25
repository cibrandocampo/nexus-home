# Upstream

- Source: https://github.com/cloudflare/security-audit-skill (skill `skills/security-audit`),
  commit c1c8a8c1471069fb0e188eeaff69b8e8db6564a8 (2026-09-14), MIT License (`LICENSE`). Vendored unchanged.
- The validators need Node.js, which is not installed on the host (Docker-first). Run them in a container,
  read-only, with no network:

  ```sh
  docker run --rm --network none -v "$PWD/.claude/skills/security-audit:/skill:ro" \
    -v "<output-dir>:/out:ro" node:24-alpine node /skill/validate-findings.cjs /out/findings.json
  ```
  (same for `validate-coverage-ledger.cjs /out/coverage-ledger.json`).
- Executing target code, which the skill allows only inside an OS-enforced sandbox, means the dev containers
  with `--network none` and a scratch copy — never the host.

To update: clone upstream, review the diff of `skills/security-audit/` (it becomes agent instructions),
copy it over and update the commit above.
