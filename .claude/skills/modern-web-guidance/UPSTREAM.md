# Upstream

- Source: https://github.com/GoogleChrome/modern-web-guidance (skill `skills/modern-web-guidance`),
  commit 2b4aa13a72dd47cd135b06ce5abfccd92e19b24f (2026-11-23), Apache License 2.0 (`LICENSE`).
- `guides/` is vendored unchanged. `guides/INDEX.md` is generated here (title and first sentence of each guide).
- `SKILL.md` is upstream's with the commands run in a throwaway Docker container instead of on the host
  (the project never runs tools on the host), the CLI pinned to `modern-web-guidance@1.0.2` instead of
  `@latest`, upstream's "Using npx / pnpx" section replaced by "Running in Docker",. (The fastapi-react-template copy adds one line about Mantine.)
- `guides/` is the offline fallback when Docker or the network is unavailable.
- Not included: upstream's `chrome-extensions` skill (not relevant to this stack).

To update: clone upstream, review the diff of `skills/modern-web-guidance/` (it becomes agent instructions),
copy `guides/`, regenerate `guides/INDEX.md`, re-apply the SKILL.md changes, check the npm version upstream's commands expect (`docker run --rm
node:24-alpine npm view modern-web-guidance version`) and update the pin and the commit above.
