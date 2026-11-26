# Garage IoT Controller v2: working notes

Last updated: 2026-11-16.

Living document with the status, decisions and open items of the rewrite.
Usage documentation (pins, API, build) is in [README.md](README.md).

## Goal

Rewrite the garage controller from scratch (Arduino UNO R4 WiFi, door + light bulb):

1. Leaner, more robust code.
2. Better web page, with action buttons.
3. An API designed so a middleware can easily expose it as a Home Assistant device.

## Current status

| What | Status |
|------|--------|
| New firmware in `firmware/` | 2.0.5. Builds for `arduino:renesas_uno:unor4wifi` (43 % flash, 61 % RAM) |
| Host test of the logic (`test/run.sh`) | **Passes** |
| Garage board | In production since 2026-11-17 (`garage-3562d4`, 10.1.3.103, modem_fw 0.6.0, RSSI -77 to -83 dBm). Installation checks done on 2026-11-19, see below |
| Web page | Works in the browser (reviewed 2026-11-19) |
| Commit | Branch `garage-v2`, pushed; PR to `main` |
| Old code (`src/`, Postman collection) | Deleted; recoverable from git |

## Blockers

- [x] `firmware/secrets.h` with WiFi credentials (git-ignored).
- [x] `g++` installed.
- [x] `arduino-cli:raw-usb` snap interface connected (host snap, no longer used: see below).
- [x] **Serial port permission.** `dialout` is active and `/dev/ttyACM0` is writable.
- [x] **Upload tool was 32-bit.** The snap's i386 `bossac` was replaced with Arduino's 64-bit build of
      the same version (checksum verified against the package index). The original is kept next to it
      as `bossac.i386.orig`. Superseded (2026-11-26): the toolchain now runs in Docker (`make help`),
      with its own 64-bit tools; the host snap is no longer used.
- [ ] Optional: add a passphrase to the SSH key (`ssh-keygen -p -f ~/.ssh/id_ed25519`, in a regular terminal).

## Board test results (2026-11-16)

Bench board: a new UNO R4 WiFi with nothing wired, not the one installed in the garage. Board at `10.1.3.114` (DHCP), id `garage-33ad84`, hostname `igarage` (does not resolve on the LAN).

- [x] Upload works; the board joins WiFi and serves the API and the page.
- [x] `test/api_smoke.sh` with `LIGHT=1`: info, state, 404, cross-origin 403, timed light.
- [x] 401 without token, 400 `invalid_duration`, light on/off/toggle, light timer expiry.
- [x] Serial log lines for state changes.
- [x] Fixed after the test: `light/on?duration=0` and `light/off` answered `ok` and bumped `rev` when
      nothing changed. They now answer `noop`. Host test extended. Uploaded and checked on the board.
- [x] Added after the test: event log (`/api/v1/log` and web page). Host test passes. Uploaded and checked on the board.
- [x] Changed after the test: button and door sensor are active low (see "Button and door sensor inputs").
      Uploaded; the board reads both as idle with the pins open. **Not tried with jumpers yet.**
- [x] Bench tests with jumpers (2026-11-17, user + log): open, open with sensor never released (`no_movement`),
      close, failed close (40 s, alert, cleared by the sensor), stop while moving, door moved without the board,
      auto light at night, light timer, busy (409 on close and stop right after open), reset reason `pin`,
      button held at boot (no pulse). All as expected.
- [ ] One event per touch: once 4 presses in 1-2 s were logged (old firmware, 344-345 s); not clarified whether it
      was one touch (bounce: raise DEBOUNCE_BUTTON_MS to 50-80) or several. Retest with the real button.
- [ ] LED matrix, WiFi loss: not tested yet.
- Bench board WiFi is weak (-80 to -89 dBm): frequent 1-6 s HTTP stalls during the tests, unrelated to presses.
- [x] Web page in a browser: works (user, firmware without the event log).
- [x] Web page review (2026-11-17): the activity list was rebuilt every second and jumped back to
      the top when scrolled; now built once per new log and only the times refresh. Older events show
      clock time instead of "25 h 0 min ago". Dark scrollbar and controls (`color-scheme`). Uploaded and checked.
      Buttons start disabled until the first state arrives. Scroll and time format checked in Chrome on the board.
- Bench board RSSI was -84 dBm on 2026-11-17 (weak); check the signal at the garage before installing.
- [x] Modem firmware version: 0.6.0 (bench board), read from `/info`.
- Seen with the old active-high inputs: with pins 9 and 11 floating the board missed and doubled button
  presses and saw phantom sensor changes. This is what led to the active-low change.
- Pin 12 still floats on the bare board: tie it to GND or 5V while testing.

## Garage installation (2026-11-17 to 2026-11-19)

Wiring changed to active low (4.7 kΩ from each input to 5V, contacts to GND), measured, v2 uploaded over USB,
then 2.0.1 to 2.0.4 over the network (`tools/update.sh`). Light sensor AO wired to A0 on 2026-11-19.
Checks on the real door (the user and Claude through the API, 2026-11-19):

| Check | Result |
|-------|--------|
| Push button | opens; logged as button |
| Remote control | same as the button: both close the same contact |
| Open and close from the web / API | work with the token; open 20 s, close confirmed by the sensor in 17 s |
| Pulse while moving | stops the door; the next pulse goes the other way (see "Assumptions") |
| Auto light at night | on when the door opens |
| Closed sensor at opening start | bounces for under 1 s: ignored for 3 s since 2.0.2 (`DOOR_SETTLE_MS`) |
| Light sensor DO (potentiometer) | badly set: "night" at midday, "day" at 982 at night. Replaced by AO + threshold in 2.0.3 |
| Light level, 2026-11-19 evening | ~700 at dusk (user: "dark, the light is welcome"), ~980 at night with the door open, ~850 with it closed |

**Going back to the old firmware** (branch `main`, `devices/garage-iot-controller/src/`): it expects the old
wiring (contacts to 5V, 4.7 kΩ to GND, 10 kΩ in series on the sensor wire), and the real WiFi credentials in
`src/wifi_manager.h` (not committed). Upload over USB with `arduino-cli compile/upload` on that folder. If only
the firmware misbehaves, stay on v2 and fix it: the wiring is already the new one.

## Decisions

### Architecture

- **Logic runs in a 100 Hz timer interrupt** (`garage.cpp`): debounced inputs, relays, door state
  machine and light timer. Reason: `WiFi.begin()` blocks the main loop for up to 10 s; this way the
  button and the relay pulse do not depend on the network.
- The main loop only handles network, HTTP, display and logging.
- If no hardware timer is free, the logic falls back to the main loop (works, without that immunity).
- Own non-blocking HTTP server with fixed buffers (no `String`). Small answers go out in a single modem write.
- WiFi status is polled every 2 s and cached; reconnection uses a growing back-off (5 s to 60 s).

### Door

- Four states: `closed`, `opening`, `open`, `closing` (the same as Home Assistant).
- **Opening:** 20 s, then the sensor is checked: not active → `open`; still active → `closed`.
- **Closing:** the door is only `closed` when the sensor says so. If it has not after 40 s → `open` + close failed.
- The remote control receiver is wired to the button input (pin 9): the board cannot tell them apart and both
  report `button`. Movements the board did not start are detected through the sensor (`last_source: sensor`); the board cannot
  know their cause, so the log only says "detected by the closed sensor".
- **Close failed** (2026-11-17): closing waits up to `DOOR_CLOSE_TIMEOUT_MS` (40 s) for the sensor; otherwise
  `open` + `door.close_failed` (API, web alert, `close_failed` event, HA `problem` binary sensor). Cleared by
  the sensor closing or a new pulse. Measured by the user: 16 s up, 19 s down, 30 s when the opener
  recalibrates after an incident. Tested on the bench board with the sensor open.
  Trade-off: `door/open` answers 409 for up to 40 s while closing. Closes with the remote are watched too (same input as the button).
- A pulse while the door is moving is treated as a stop.
- At least 1.2 s between pulses.

### Button and door sensor inputs

- **Active low with the internal pull-up** (changed on 2026-11-16): the button connects pin 9 to GND and
  the door sensor connects pin 11 to GND while the door is closed.
  Reason: wired to 5V without a pull-down, the pin floated between presses and the bench board missed or
  doubled presses. Active low needs no extra part and a loose wire is the safe case.
- In the real installation this means moving the second wire of each contact from 5V to GND at the board.
  The doorbell push buttons themselves do not change.
- **The real installation has pull-down resistors on pins 9 and 11 (4.7 kΩ, per the user). They must come
  out**, or be moved to 5V as external pull-ups: left to GND they hold the pins low (pressed / closed).
- With this wiring no 5V leaves the board on the sensor cable, which also removes the old "pin 11 resets
  the board" issue (the 10 kΩ series resistor is no longer needed).
- `BUTTON_ACTIVE_LOW` / `DOOR_SENSOR_ACTIVE_LOW` = false restore the old wiring.

### LED matrix (debug panel)

- Purpose: debugging, not informing the user. The door and the light are visible on site; full
  information is on the web page and the API.
- Top, inputs: a letter appears while the input is active. `N` night, `C` door sensor closed, `B` button.
- Bottom, outputs: a bar lights while active. Light relay, door relay, WiFi (blinks while disconnected).
- Rejected: icons (sun, moon, bulb...). Not readable at 12x8.
- Button presses and relay pulses stay visible for at least 0.7 s.
- Full IP after connecting (octet by octet) and last octet every 30 s (`DISPLAY_IP_EVERY_S`).

### Watchdog

- The hardware watchdog (5 s, max ~5.6 s) cannot be fed from the main loop: `WiFi.begin()` blocks up to 10 s.
- It is fed from the 100 Hz timer interrupt, only while the main loop has sent a heartbeat in the last 60 s.
  Interrupt stuck → reset within 5 s. Main loop stuck → reset after ~60 s. One mechanism covers both.
- Not started when the logic runs from the main loop (no hardware timer): it would reset during `WiFi.begin()`.
- Reset cause read from `RSTSR0/1` at boot and cleared, exposed as `reset_reason` in `/info` and on the web page;
  `watchdog_reset` event logged. The bootloader does not clear the flags (checked on the board).
- Bench test 2026-11-17 with `WATCHDOG_SELFTEST`: loop hang → reset ~60 s later; interrupts off → reset ~5 s later;
  `reset_reason: watchdog` and the event in the log in both cases. Normal build stable past 60 s.

### Light

- Turns on for 120 s when the door starts opening at night, whatever opened it.
- From web/API: with a duration or without a timer (`duration=0`).
- A light switched on manually without a timer is not shortened by the automatic one.

### API (`/api/v1`)

- One resource per entity: `/door/{open,close,stop,toggle}`, `/light/{on,off,toggle}`, `/state`, `/info`, `/log`.
- Idempotent commands: asking for the current state returns 200 with `"result":"noop"`, for the door
  and for the light. `light/on` with a duration always restarts the timer, so it answers `ok`.
- Every command returns the complete new state.
- 409 `door_busy` when the opposite movement is in progress or a pulse was sent too recently.
- `/info` describes the device and its entities (cover, light, binary_sensor, sensor) for the middleware,
  and reports the WiFi module firmware (`modem_fw`).
- `rev` in the state: counter that increases on every change.
- The old endpoints (`/status`, `/set`) are gone.

### Event log

- Ring buffer with the last 64 events in RAM (`LOG_SIZE`), served by `GET /api/v1/log` and shown on the
  web page as "Recent activity". Lost on reset: accepted, persistence was not worth the complexity.
- Bounded by count, not by time: on a quiet day it covers much more than one hour; with floating
  inputs on the bench it fills in minutes.
- Timestamps are uptime seconds (the board has no clock); the client turns them into "x ago".
- The tick counter is 64-bit, so uptime, door "since" and log ages do not wrap after 497 days
  (covered by the host test). All `millis()` uses in the main loop are differences, safe across its 49-day wrap.
- Costs about 4 KB of RAM (log, copy and a 4 KB JSON buffer): 34 % → 47 %.

### Security

- Token from the stored settings required on POST and on `GET /settings`.
- POSTs whose `Origin` differs from `Host` are rejected (another web site open in a LAN browser cannot open the door).
- GETs are open. Everything is plain HTTP.

### Language

- Everything in the repository is in English: code, comments, web page, documentation and these notes.

## Assumptions to confirm

- [x] **Door movement time:** 20 s, confirmed.
- [x] **A pulse while moving stops the door** (confirmed by the user and on the real door, 2026-11-19). The next
      pulse goes the other way: stopped while closing, it opens. Before 2.0.4 the board showed "closing" and
      raised a false close_failed after 40 s. 2.0.4 remembers the direction (see README, "Stopped part way").
      2.0.5 reports it (`door.stopped`) so the web page offers Open, and `/door/open` no longer ignores a door
      stopped while closing.
- [ ] **Default light duration through the API:** 120 s. For Home Assistant, no timer may be better.
- [x] Input wiring in the real installation (per the user, from memory, "I think 4.7 kΩ"): pull-downs to
      GND on pins 9 and 11; pin 12 is the usual LDR circuit and stays active high. The old documentation
      (README at commit `1570509`) only mentions a 10 kΩ series resistor on the door sensor's 5V line,
      "to prevent board resets". The user is going to photograph the installation.
- [x] The board on the USB cable is a bench board with nothing wired: door commands can be tested freely.
- [x] Modem firmware version of the board installed in the garage: 0.6.0 (network updates need 0.5.0+).

## Interrupt analysis (checked against core 1.6.0 sources)

- `WiFi.begin()` blocks up to 10 s on the main thread with interrupts enabled: confirmed.
- Priorities: timer 8, modem UART 12. The 100 Hz routine delays the UART by microseconds; the modem never delays the logic.
- Shared state is only touched from the interrupt or with interrupts disabled. No races found.
- The LED matrix uses a different timer.
- ~~Gap: no watchdog.~~ Closed on 2026-11-17, see "Watchdog" under Decisions.

## To do, in order

1. [x] Clear the blockers above.
2. [x] Run `test/run.sh`.
3. [x] Upload to the bench board and test web and API (`test/api_smoke.sh`).
4. [ ] Finish the bench tests with jumpers: button, door sensor, door commands, LED matrix, WiFi loss
      (list in NEXT_SESSION.md).
5. [x] Rewire the real installation for the active-low inputs and confirm the assumptions (2026-11-19, see
      "Garage installation").
6. [x] **Watchdog** (2026-11-17): see "Watchdog" under Decisions. Tested on the bench board.
7. [x] **Stored settings, WiFi setup mode and restart button** (2026-11-17): see README, "First setup" and "Stored settings".
   One binary for every door, with no secrets in it. Checked on the bench board: setup page from a phone, restart
   from the web, settings kept after a firmware upload over USB, 401/403 on settings and restart without token.
   WiFi change with a wrong password: back on the old network after ~70 s, `wifi_change_failed` logged (2026-11-17).
   Fixed after that test: an unchanged save was logged as `settings_changed` (bytes after a string's end compared).
   **Still to check:** how long a flash save blocks (door timer jitter).
8. [x] **OTA** (2026-11-17): `tools/update.sh` from a computer in the LAN, see "OTA: network updates" below.
8b. [ ] **Update server**: small Docker container on the user's server (LAN, plain HTTP) serving the .ota files;
    later the Home Assistant gateway.
9. [x] Commit on the branch `garage-v2` (2026-11-17), pushed and PR opened (2026-11-19).
10. [ ] Home Assistant middleware.
11. [ ] **WiFi network picker** (agreed with the user on 2026-11-19, for after 2.0.3): a list of the networks
    found instead of typing the SSID.
    - Setup mode: scan at boot *before* `WiFi.beginAP()` (the AP is started in mode 2, AP only, and it is not
      known whether the module firmware can scan with the AP up). Keep up to ~20 networks, one per SSID with the
      best RSSI, sorted by signal; serve them on a setup-only endpoint (e.g. `GET /api/v1/setup/networks`).
    - Setup page: a select with the signal bars of the status block, a lock for protected networks, and
      "Other network…" to type a hidden SSID; an open network hides the password field.
    - "Scan again" button only if a scan with the AP up works on the bench board (try it there); otherwise
      restarting in setup mode refreshes the list.
    - Also in Settings (normal mode, to change network): scanning while connected as a station is fine.
    - `WiFi.scanNetworks()` (WiFiS3, core 1.6.0) sends `AT+WIFISCAN` and returns SSID, RSSI and encryption.

## OTA: network updates

**Done on 2026-11-17** (usage in README, "Firmware update over the network").

Decisions (with the user):
- One device for now: no permanent update infrastructure. `tools/update.sh` on a computer in the LAN builds,
  serves the file for a moment and asks the board to install it. Goal: no PC cable to update.
- Next feature: a small Docker container on the user's server, in the same LAN, serving the files over plain
  HTTP (no HTTPS: LAN only, the binary holds no secrets, the board only downloads on a token-authenticated
  request). That container will later become the gateway to Home Assistant.
- Rejected: GitHub releases served directly (redirects, which the module does not follow; certificates that
  change); a public server with HTTPS (not needed for one device in the LAN).

How it works: `POST /api/v1/firmware {"url"}` → HEAD check of the URL with a plain connection → module download
(`OTAUpdate::startDownload` + `downloadProgress`, needs module firmware 0.5.0+) → `verify()` (magic + CRC of the
.ota) → answer `flashing` → `update(path)`: the module resets the RA4M1 into its bootloader and flashes it.

`.ota` format (from Arduino's bin2ota.py and the module's decoder, read on 2026-11-17): uint32 LE length (bytes
from offset 8), uint32 LE CRC-32 (zlib) of those bytes, magic 0x23411002, 8-byte version `00..00 40`, LZSS
payload (EI=11, EJ=4, ring 2048 bytes starting at 2032, MSB-first, flag 1 = literal). The module always decodes
LZSS (the compression flag is ignored). `tools/make_ota.py` writes it in pure Python and checks it by decoding.

Bench results (2026-11-17, module firmware 0.6.0):
- Four network updates OK (2.0.0 → 2.0.1-test → 2.0.0 → 2.0.1-test → 2.0.2-test → 2.0.0): download of ~81 KB in
  about 3.5 s, back online with the new version about 20 s later, settings kept, `reset_reason: pin`.
- Pin 3 (door relay) with a multimeter: 0 V at power-on, 0.2 V while the board is reflashed and restarts, no
  pulse. Recommendation in README: 10 kΩ from pins 2 and 3 to GND in the installation.
- **Module bug 1 — its file write command (`AT+FS`):** after any error while saving a chunk it returns without
  resuming its command parser and stops listening to the board until a power cycle (its source: `+FS` handler
  in cmds_esp_generic.h skips `srv.continue_read()` on errors; also `uint8_t` size, max 255 bytes per write).
  Hit twice on the first chunk. That killed the first design (upload the file from the web page). Not used.
- **Module bug 2 — its download of a URL that does not answer** hangs the module (network, web and the USB serial,
  which goes through the module) for several minutes at least. Seen once with a closed port. Mitigation: the
  board checks the URL with a HEAD request first (`server_unreachable` in 10 s, `file_not_found` at once);
  tested with a closed port, a missing host and a missing file: the board kept answering in all three.
- On this board the USB serial port goes through the WiFi module: when the module hangs, the serial port is
  silent too. Reading the serial port: `stty -F /dev/ttyACM0 115200 raw -echo; cat /dev/ttyACM0`
  (`arduino-cli monitor` gave no output when not run in a terminal).

Open:
- [ ] Does the module come back by itself after bug 2, and after how long? (Power cycle was used.)
- [x] Module firmware of the board in the garage: 0.6.0, network updates work (2.0.1 to 2.0.3, 2026-11-19).
- [ ] No rollback: a firmware that boots without network needs USB. Always try a build on the bench board first.

## Parked ideas

- Real-time notifications to the middleware (SSE or webhook) instead of polling.
- mDNS (`garage.local`) for discovery.
- MQTT with Home Assistant auto-discovery as an alternative to the middleware.
