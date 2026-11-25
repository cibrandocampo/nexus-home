# Upstream

- Source: https://github.com/GoogleChrome/modern-web-guidance (skill `skills/modern-web-guidance`),
  commit 2b4aa13a72dd47cd135b06ce5abfccd92e19b24f (2026-11-23), Apache License 2.0 (`LICENSE`).
- `guides/` is vendored unchanged. `guides/INDEX.md` is generated here (title and first sentence of each guide).
- `SKILL.md` is upstream's with one change: the npx CLI (`search`, `retrieve`, `legacy-scan`) is replaced by
  reading the vendored guides, because the project does not run third-party code on the host or download it at
  run time. Upstream's "Using npx / pnpx" section is removed; the rest is upstream text.
- Not included: upstream's `chrome-extensions` skill (not relevant to this stack).

To update: clone upstream, review the diff of `skills/modern-web-guidance/` (it becomes agent instructions),
copy `guides/`, regenerate `guides/INDEX.md`, re-apply the SKILL.md change, update the commit above.
