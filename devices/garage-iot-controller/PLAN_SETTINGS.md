# Plan: settings stored on the board, WiFi setup mode and restart button

Status: **implemented on 2026-11-17** and set up on the bench board by the user (setup page, restart from the
web). User documentation is in README.md ("First setup"). Remaining checks are in NOTES.md.
Agreed with the user on 2026-11-17.
Context and other decisions are in [NOTES.md](NOTES.md).

## Why

Today the WiFi credentials and the API token are compiled in (`secrets.h`), and the door timings are in
`config.h`. That means one binary per door, and an `.ota` file that carries the WiFi password.

With the settings stored on the board:

- **One binary for every door.** An OTA update works for all of them.
- **The binary holds no secrets**, so it can be served from the update server without leaking the
  WiFi password (this removes one of the OTA risks listed in NOTES.md).
- A new door can be installed without a build environment.
- The door timings can be adjusted per door without rebuilding.

## Behaviour

### No settings: no WiFi

- If no settings are stored, the board does not join any network.
- Door, button, remote control (pin 9), sensor and automatic light keep working: they run in the
  timer interrupt and do not depend on the network.
- The LED matrix shows that the board is not configured (exact symbol to be decided).

### Setup mode (physical jumper)

- Entered **only** when the setup pin is tied at boot. Nothing else opens the setup network: not a WiFi
  loss, not an API call. This keeps it out of reach of anyone without physical access.
- Proposed pin: **pin 7 to GND**, `INPUT_PULLUP`, like the matrix pin 6. No extra part needed.
  **To be confirmed by the user.**
- In setup mode the board starts its own open access point, `Garage-<id>` (for example `Garage-33ad84`),
  and serves a setup form at `http://192.168.4.1/`.
- The setup network is open and plain HTTP. Accepted by the user: it is only used during this operation
  and with physical access to the board.
- After saving: remove the jumper and restart (or the board restarts by itself and stays in setup mode
  only while the jumper is in place).
- The board cannot be on the home WiFi and run its own network at the same time (assumed for `WiFiS3`,
  to check), so in setup mode there is no normal web page or API.

### Settings stored

| Setting | Default | Notes |
|---------|---------|-------|
| WiFi network (SSID) | empty | empty = no WiFi |
| WiFi password | empty | never returned by the API or shown on the page |
| API token | empty | required for POST commands and for changing settings |
| Device name | `Garage` | shown on the page, in `/info` and in Home Assistant |
| Opening time | 20 s | `DOOR_TRAVEL_MS` today (measured: 16 s) |
| Close confirmation timeout | 40 s | `DOOR_CLOSE_TIMEOUT_MS` today (measured: 19 s, 30 s when recalibrating) |

- Possible later additions: automatic light duration, automatic light on/off, LED matrix IP display.
- Values in `config.h` stay as the defaults used when nothing is stored.
- Each value is checked before saving (sensible ranges for the timings, lengths for the strings).
- Stored in the board's data flash (`EEPROM` library) with a version number and a checksum, so an
  empty or corrupted area falls back to the defaults instead of loading garbage.
- **To check on the bench board:** that the stored settings survive a firmware upload over USB and an OTA update.
- The data is not encrypted on the board. Accepted: whoever can read it over USB has physical access
  and could open the door anyway.

### Settings page (normal mode)

- A "Settings" section on the web page, protected with the token.
- New API endpoints (token required):
  - `GET /api/v1/settings`: current settings, without the WiFi password.
  - `POST /api/v1/settings`: change one or more settings.
- **Changing the WiFi from the web:** a typo in the password would leave the board offline and need a
  trip to the garage with the jumper. To avoid that, the board tries the new network and, if it cannot
  connect within about a minute, goes back to the previous one.
- New timings apply to the next door movement, not to one in progress.

### Restart button

- A "Restart" button on the web page, with a confirmation step.
- `POST /api/v1/restart` (token required). Answers first, then restarts after a short delay so the
  answer reaches the client.
- Refused with 409 while the door is moving, so a restart never cuts a movement half way.
- Logged as an event before restarting; the log itself is lost on restart (it is in RAM), so the
  reason is only visible in the serial log. A boot reason in `/info` could be added later.

### Development

- `secrets.h` goes away: one single path. The bench board is configured once with the jumper like any
  other.

## Order

1. Software watchdog (already planned).
2. This plan: stored settings, setup mode, settings page, restart button.
3. OTA, which then serves a single binary without secrets.

## Open questions

- [x] Setup pin: pin 7 to GND.
- [x] LED matrix: `SET` in setup mode; WiFi bar off when not configured.
- [ ] Does `WiFiS3` allow its own network and the home WiFi at the same time? Not needed so far (not used).
- Differences from this plan: the restart is not logged (the log is in RAM and lost anyway); `secrets.h` is no
  longer read but the git-ignored file may still exist on the development machine.
