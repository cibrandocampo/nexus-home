# Changelog

All notable changes to the nexusHome platform. Versions follow [Semantic Versioning](https://semver.org/);
a published GitHub release `platform-vX.Y.Z` publishes the image tags `X.Y.Z` and `stable`.

## Unreleased

### Added
- Platform created from [fastapi-react-template](https://github.com/cibrandocampo/fastapi-react-template)
  `af8fea9`: sign-in with an emailed code or a password, users and roles, profile (language, colour
  scheme, time zone), one production image with PostgreSQL 19, end-to-end tests (see `TEMPLATE.md`).
- Devices (phase 2): registry by LAN scan or address with tokens encrypted at rest (a board without a
  token gets one), state polling with online/offline and restarts, event history collected from the
  boards with who sent each command, commands with an audit trail, the boards' settings, restart and
  token rotation; dashboard, device pages, history and device administration (en, es, gl).
- Garage board simulator (`simulator/`) for the dev stack, the tests and the end-to-end suite.
