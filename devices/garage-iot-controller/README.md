# Garage IoT Controller

Firmware for an Arduino UNO R4 WiFi that drives a garage door opener and a light.
It serves a web page with action buttons and a small REST API designed to map
one-to-one onto Home Assistant entities.

## Hardware

| Pin | Mode | Function |
|-----|------|----------|
| 2 | OUTPUT | Light relay (HIGH = on) |
| 3 | OUTPUT | Door opener relay (400 ms HIGH pulse) |
| 7 | INPUT_PULLUP | Setup jumper: tied to GND at boot = setup mode (see "First setup") |
| 9 | INPUT_PULLUP | Push button, wired between the pin and GND (LOW = pressed) |
| 11 | INPUT_PULLUP | Door sensor, contact between the pin and GND (LOW = closed) |
| A0 | analog | Light sensor level (AO of the LDR module, 0-1023, higher = darker) |
| LED_BUILTIN | OUTPUT | On while the door is not closed |

### Wiring

```
                         5V
                          |
                    [4.7k - 10k]   optional external pull-up, recommended for long cables
                          |
 pin 9  ------------------+------ push button ------ GND     pressed = LOW
 pin 11 ------------------+------ door contact ----- GND     door closed = LOW
        (one resistor per pin)

 A0     <----- AO of the LDR module (module powered from 5V and GND)     higher = darker
 pin 2  -----> light relay                                   on = HIGH
 pin 3  -----> door opener relay                             400 ms HIGH pulse
 pin 2, pin 3 ---[10k]--- GND                                recommended, see below
```

- **Button and door sensor (pins 9 and 11)** are plain contacts to GND. The internal pull-up keeps the
  pin at 5V, so a loose or broken wire reads "not pressed" and "door not closed", and no 5V leaves the
  board on those cables.
- The internal pull-up is weak (tens of kΩ). For long cable runs add an external one, 4.7 kΩ to 10 kΩ
  from the pin to 5V.
- **Never leave a pull-down resistor on pins 9 or 11.** Against the pull-up it holds the pin low, which
  reads as pressed / closed all the time.
- **Relay outputs (pins 2 and 3):** while the board restarts or is reflashed, these pins are not driven.
  On the bench pin 3 read 0 V at power-on and rose to 0.2 V during a network update (no pulse), far below
  what a relay input needs. In the installation, with long cables near the motor, add a **10 kΩ resistor from
  each relay pin to GND** so a floating pin cannot pick up noise, unless the relay module already has one.
- **Light sensor (A0)** is the analog output (AO) of a standard LDR module. Night is decided by the board
  from the level and a threshold set on the web page, so the module's potentiometer and its digital output
  (DO) are not used since 2.0.3. With A0 left open the reading floats (around 200 on the bench board).

Coming from the previous wiring (contacts to 5V with pull-downs to GND): move the second wire of each
contact from 5V to GND, and move the pull-down resistors to 5V or remove them. To keep the previous
wiring instead, set `BUTTON_ACTIVE_LOW` and `DOOR_SENSOR_ACTIVE_LOW` to `false` in `config.h`.

### Bench testing on a bare board

| Pin | Idle | Active |
|-----|------|--------|
| 9 | leave open | touch to GND = button pressed |
| 11 | leave open = door not closed | jumper to GND = door closed |
| A0 | jumper to GND = 0, bright (it floats if left open) | jumper to 5V = 1023, dark |

Pins 2 and 3 are outputs: measure them (multimeter, or an LED with a resistor to GND), never tie them
to 5V or GND.

## Behaviour

**Door.** The opener is a single-button type: every relay pulse starts, stops or
reverses it. The only feedback is the "closed" sensor, so the firmware tracks four states:

| State | Entered when | Left when |
|-------|--------------|-----------|
| `closed` | sensor reads closed | a pulse is sent, or the sensor releases without a pulse from the board |
| `opening` | pulse while closed, or sensor released | after `DOOR_TRAVEL_MS`: sensor not closed → `open`, sensor closed → `closed` |
| `open` | opening finished, or a pulse stopped the door | a pulse is sent → `closing` (or `opening` if the door was stopped while closing); sensor closes → `closed` |
| `closing` | pulse while open | sensor closes → `closed`; sensor still not closed after `DOOR_CLOSE_TIMEOUT_MS` → `open` and close failed |

**Stopped part way.** A pulse stops a moving door, and the opener goes the other way on the next pulse
(checked on the real door on 2026-11-19): stopped while opening, it closes; stopped while closing, it opens.
The board remembers the direction (`door.stopped` in the state), so the button, the remote and `/door/toggle`
are always shown right, and both `/door/open` and `/door/close` work. When
`/door/close` is asked for a door stopped while closing (or `/door/open` for one stopped while opening), one
pulse would move it the wrong way, so the board sends three, as a person would: the door goes the wrong way
for about a second, stops, then goes where it was asked (`DOOR_PULSE_GAP_MS` apart). A press of the button
or `/door/stop` cancels the pulses still to send (a stop sent during the first pulse waits for the gap,
then stops the door, so it never keeps going the wrong way); other commands answer 409 `door_busy` meanwhile.

The door is only reported `closed` when the sensor says so. `DOOR_TRAVEL_MS` (opening) is 20 s and
`DOOR_CLOSE_TIMEOUT_MS` is 40 s (measured: 16 s up, 19 s down, up to 30 s when the opener recalibrates
after an incident).

**Close failed.** When a close sent by the board (button, web or API) is not confirmed by the sensor within
`DOOR_CLOSE_TIMEOUT_MS`, the door goes to `open`, `door.close_failed` becomes `true`, a `close_failed`
event is logged and the web page shows a red alert. It clears when the sensor reports closed or on the next
pulse. Stopping a close on purpose is not a failure. The remote control is wired to the button input, so
its closes are watched too. Only a door moved without the board (by hand) cannot be watched.
Pulses are at least `DOOR_PULSE_GAP_MS` (1.2 s) apart.

**Light.** Turns on for the light time (setting, 120 s by default) when the door starts opening at night,
whatever opened it. It can also be switched from the web or the API, with a timer or without one.

**Night.** From the light level on A0 (sampled once per second): night from the night level (setting, 700 by
default) up, back to day only below that level minus 30 (`NIGHT_HYSTERESIS`), so a level near the threshold
does not flip it. A change must hold for 60 s (`DEBOUNCE_NIGHT_MS`). The sensor sees the garage light, so it
is not read while the light is on and for 10 s after (`LAMP_SETTLE_MS`).

**Button.** A press sends one pulse to the opener, exactly like the opener's own button.

**Robustness.** Inputs, relays, the door state machine and the light timer run from a
100 Hz hardware timer interrupt. The button and the relay timing keep working while the
WiFi modem is busy (a reconnection attempt blocks the main loop for up to 10 s).

**Watchdog.** The hardware watchdog (5 s, `WATCHDOG_HW_MS`) is refreshed from that interrupt, and only
while the main loop has run within the last 60 s (`WATCHDOG_LOOP_S`). If the door logic stops, the board
resets within 5 s; if the main loop (network, web) hangs, it resets after about 60 s. A `watchdog_reset`
event is logged after such a reset, and `/info` reports the cause of the last start in `reset_reason`.
A reset switches the relays off; the door state is read again from the sensor.

**LED matrix.** A debug panel showing what the board reads and drives:

```
 day, closed      night, open,     night, closed,
 WiFi ok          button, relays   light on, no WiFi
 ·····██·····     █·█·····██··     █·█··██·····
 ····█·······     ███·····█·█·     ███·█·······
 ····█·······     ███·····██··     ███·█·······
 ····█·······     ███·····█·█·     ███·█·······
 ·····██·····     █·█·····██··     █·█··██·····
 ············     ············     ············
 ········███·     ███·███·███·     ███·········
 ········███·     ███·███·███·     ███·········
```

- Rows 0-4, inputs: a letter appears while the input is active. `N` = night (light sensor),
  `C` = door sensor closed, `B` = button pressed.
- Rows 6-7, outputs: a bar lights while active. Left = light relay, middle = door relay,
  right = WiFi (blinks while disconnected).
- Button presses and relay pulses stay on screen for at least 0.7 s.
- The full IP is shown octet by octet after connecting, and the last octet every
  `DISPLAY_IP_EVERY_S` (30 s). Dots on the bottom row tell which octet is on screen.

## First setup

The firmware holds no WiFi credentials or token: every door runs the same binary and keeps its own
settings in the board's data flash. A board with no settings does not use WiFi at all; door, button
and automatic light work as usual, and the WiFi bar of the LED matrix stays off.

1. Put a jumper from **pin 7 to GND** and press reset. The LED matrix shows `SET`.
2. Join the open WiFi network named after the board (`garage-xxxxxx`, the end of its MAC address) and
   open `http://192.168.4.1/`.
3. Fill in the device name, the WiFi network and password, the access token (the page can generate one;
   write it down) and the door timings. Save.
4. Remove the jumper and press **Restart**. The board joins the WiFi network.

Only the jumper opens setup mode: no WiFi loss and no API call can. The setup network is open and plain
HTTP, which is accepted because it is only up while someone with physical access configures the board.
In setup mode only the setup page and `/info` work.

### Stored settings

| Setting | Default | Notes |
|---------|---------|-------|
| Name | `Garage` | shown on the page, in `/info` and in Home Assistant |
| WiFi network and password | empty | empty network = no WiFi |
| Access token | empty | required for commands, settings and restart (8 to 64 characters, no spaces) |
| Opening time | 20 s (`DOOR_TRAVEL_MS`) | 5 to 100 s |
| Close confirmation | 40 s (`DOOR_CLOSE_TIMEOUT_MS`) | 10 to 100 s |
| Light time | 120 s (`LIGHT_DEFAULT_S`) | 10 to 600 s (10 min); auto light, and `/light/on` or `/light/toggle` without a duration |
| Night level | 700 (`NIGHT_LEVEL_DEFAULT`) | 1 to 1023; the web page shows the current level and can copy it |
| LED matrix | on | switched from the Status block of the web page (`display` in `/settings`); replaces the pin 6 jumper used up to 2.0.2 |

- Two copies are kept in two flash blocks, each with a CRC; a save writes the older one. A power cut during a
  save keeps the previous settings. They survive firmware uploads over USB (checked on the bench board).
- Settings saved by 2.0.0-2.0.2 (older format) are read after updating to 2.0.3, with the new fields at their
  defaults (checked on the bench board); the next save writes the new format.
- The web page shows the timings and the night level as sliders with these ranges. A stored value outside a
  range (2.0.0-2.0.2 allowed up to 120 s opening and 180 s close) is brought into range when loaded.
- After a normal start the settings can be changed from the web page (see below). New timings apply from the
  next door movement.
- **Changing the WiFi network from the web page:** the board tries the new network first and saves it only once
  it connects. If it has not connected within 60 s (`WIFI_TRIAL_S`), it goes back to the previous network.
- The settings are stored unencrypted: anyone who can read the board over USB can read them, but that person
  also has physical access to the door.

## Web

Open `http://<device-ip>/`. The page shows the door and light state and has buttons to
open, close, stop and pulse the door, and to switch the light with a chosen duration.
It refreshes every 1.5 seconds. A red alert appears when a close was not confirmed.
A "Recent activity" list shows the event log: events from the last
hour with a relative time ("5 min ago"), older ones with the clock time of the browser.

A folded "Settings" section changes the name, the door timings, the WiFi network and the token, and
has a "Restart controller" button. It needs the token, like the action buttons.

## API

Base path `/api/v1`. All answers are JSON.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/state` | Current state |
| GET | `/info` | Device identity and entity list |
| GET | `/log` | Recent events, newest first |
| POST | `/door/open` | Open; no-op if fully open or opening (a door stopped part way is opened) |
| POST | `/door/close` | Close; no-op if already closed or closing (a door stopped part way is closed) |
| POST | `/door/stop` | Stop a moving door (inside the 1.2 s pulse gap the stop pulse is sent when the gap ends); no-op otherwise |
| POST | `/door/toggle` | Raw pulse, same as the physical button |
| POST | `/light/on` | Light on. `duration` in seconds (default 120, `0` = no timer) |
| POST | `/light/off` | Light off |
| POST | `/light/toggle` | Toggle the light |
| GET | `/settings` | Stored settings, without the WiFi password or the token (token required) |
| POST | `/settings` | Change settings: JSON body with any of `name`, `open_s`, `close_s`, `light_s`, `night_level`, `display` (true/false), `token`, `wifi_ssid`, `wifi_password` |
| POST | `/restart` | Restart the board; 409 `door_busy` while the door moves |
| POST | `/setup` | Setup mode only, no token: save all settings from the setup page |
| POST | `/firmware` | Network update: JSON body `{"url": "http://...ota"}` (see "Firmware update over the network") |

`duration` is accepted as a query parameter (`?duration=600`) or in a JSON body (`{"duration": 600}`).

### State

```json
{
  "rev": 42,
  "uptime_s": 86400,
  "door": {"state": "closed", "moving": false, "sensor_closed": true, "close_failed": false, "stopped": "none", "since_s": 3600, "last_source": "api"},
  "light": {"state": "off", "timed": false, "remaining_s": 0},
  "night": false,
  "light_level": 512,
  "button": false,
  "display": true,
  "wifi": {"ip": "192.168.1.190", "rssi": -58}
}
```

- `door.state`: `closed`, `opening`, `open` or `closing`.
- `door.close_failed`: `true` when the last close was not confirmed by the sensor (see Behaviour).
- `door.stopped`: with `door.state` `open`, whether a pulse stopped the door part way and which way it was
  going: `up` (the next pulse closes it), `down` (the next pulse opens it) or `none` (fully open, or not
  `open`). The web page shows "Stopped part way" and enables both Open and Close.
- `door.last_source`: `button` (push button or remote control, both wired to pin 9), `api`, `sensor` (change detected by the closed sensor without a pulse from this board: by hand or another remote) or `none` (nothing since the last restart). The web page shows it under the door state.
- `light_level`: light sensor reading (AO, pin A0), 0-1023, higher = darker, averaged once per second.
  `night` is decided from it (see Behaviour). It does not change `rev`.
- `rev` increases on every change, so a client can skip unchanged polls.

### Event log

`GET /log` returns the last 64 events (`LOG_SIZE` in `config.h`). They are kept in RAM, so a
reset or power cut clears them.

```json
{"uptime_s": 5400, "events": [
  {"t": 5310, "event": "light_off", "source": "auto", "reason": "none", "value": 0},
  {"t": 5210, "event": "door_open", "source": "button", "reason": "travel_end", "value": 0},
  {"t": 5190, "event": "light_on", "source": "auto", "reason": "none", "value": 120},
  {"t": 5190, "event": "door_opening", "source": "button", "reason": "command", "value": 0}
]}
```

Each entry is one step: what changed (`event`), who started it (`source`) and why (`reason`).
The web page shows them as "what happened" with the cause below, for example
"Door opening / Push button or remote · door was closed".

- `t` is the uptime in seconds when the event happened: `uptime_s - t` is how long ago.
- `event`: `boot`, `door_closed`, `door_opening`, `door_open`, `door_closing`, `close_failed`, `light_on`,
  `light_off`, `night`, `day`, `button_ignored`, `wifi_up`, `wifi_down`, `watchdog_reset`, `settings_changed`,
  `settings_save_failed`, `wifi_changed`, `wifi_change_failed` or `setup_mode`.
  A button press that fires the relay is logged as the door event it causes; `button_ignored` is a press
  that came less than 1.2 s after the previous pulse. `close_failed` replaces `door_open` when a close times out.
- `source`: `button` (push button or remote), `api`, `sensor` (detected by the closed sensor, not started by the board), `auto`
  (light timer or automatic light) or `none`.
- `reason` (door events):

| Reason | Event | Meaning |
|--------|-------|---------|
| `command` | `door_opening`, `door_closing` | pulse with the door stopped |
| `stopped` | `door_open`, `door_closed` | pulse while moving: the door stopped |
| `travel_end` | `door_open` | opening time over, sensor not closed |
| `no_movement` | `door_closed` | opening time over, sensor never released: the door did not move |
| `sensor_closed` | `door_closed` | closed sensor activated (confirming a close, or with no command from the board) |
| `sensor_released` | `door_opening` | closed sensor released with no command from the board |
| `came_back` | `door_closed` | closed sensor active again during an opening |
| `too_soon` | `button_ignored` | less than 1.2 s since the last pulse |
| `startup` | `door_open`, `door_closed` | state read from the sensor at boot |

- `value`: timer in seconds for `light_on` (`0` = no limit) and timeout in seconds for `close_failed`.

### Commands

Commands are idempotent and answer with the new state, so no second request is needed:

```json
{"result": "ok", "state": { ... }}
```

`result` is `ok` when something was done and `noop` when the device was already in the requested state.

### Errors

```json
{"error": {"code": "door_busy", "message": "Door is moving or was just triggered, retry later"}}
```

| Status | Code | Meaning |
|--------|------|---------|
| 400 | `invalid_duration` | `duration` is not a number between 0 and 86400 |
| 401 | `unauthorized` | Token missing or wrong |
| 403 | `forbidden` | Cross-origin browser request |
| 404 | `not_found` | Unknown path or command |
| 405 | `method_not_allowed` | Wrong HTTP method |
| 409 | `door_busy` | Opposite movement in progress, or a pulse was sent less than 1.2 s ago; restart while moving |
| 400 | `invalid_*` | A setting is out of range or too long (the code names the field) |
| 500 | `save_failed` | The settings could not be written to flash |
| 502 | `server_unreachable`, `file_not_found`, ... | Firmware update: the file could not be fetched or checked |

`POST /settings` answers `{"result": "ok", "settings": {...}}`, or `"result": "testing_wifi"` when the WiFi
network changes: the board then drops the connection to try the new network.

### Security

- The access token from the settings is required as `Authorization: Bearer <token>` on every POST and on
  `GET /settings`. The web page asks for it once and remembers it in the browser.
- POST requests carrying an `Origin` header that differs from `Host` are rejected, so
  another web site open in a browser on the LAN cannot operate the door.
- GET requests are always open. The device speaks plain HTTP: keep it on a trusted network.

### Home Assistant mapping

| Entity | Type | State | Commands |
|--------|------|-------|----------|
| Door | `cover` (`device_class: garage`) | `door.state` (same four values as HA) | `open_cover` → `/door/open`, `close_cover` → `/door/close`, `stop_cover` → `/door/stop` |
| Light | `light` | `light.state` (`on`/`off`) | `turn_on` → `/light/on?duration=0`, `turn_off` → `/light/off` |
| Door problem | `binary_sensor` (`device_class: problem`) | `door.close_failed` | |
| Night | `binary_sensor` | `night` | |
| Light level | `sensor` (raw, higher = darker) | `light_level` | |
| Signal | `sensor` (`signal_strength`, dBm) | `wifi.rssi` | |

Home Assistant disables "open" on an `open` cover without a position. For a door stopped part way
(`door.stopped` not `none`) the middleware should report a position between 0 and 100 (e.g. 50), so both
open and close are offered.

`GET /info` returns the device id, name, model, firmware version, WiFi module firmware
(`modem_fw`), mode (`normal`, `setup` or `unconfigured`), cause of the last start (`reset_reason`: `power`,
`pin` for the reset button, `software` after a firmware upload or a restart, or `watchdog`), MAC, hostname
(the device id) and this entity list, which is what a middleware needs to register the device.

## Platform

The nexusHome platform (`platform/`) manages this board through the API above: it finds it with a
scan of the LAN, keeps its state and event history (with who sent each command), sends commands and
changes its stored settings and token. A board added without a token gets one from the platform; its
administrators can show it for this web page. The simulator in `platform/simulator` speaks the same
API for the platform's tests, and its contract test fails when this README or `firmware/http.cpp`
change the API: update the simulator with them.

## Build and upload

The toolchain runs in Docker (`docker/Dockerfile`: `g++`, `python3`, `arduino-cli` 1.6.0 and the
`arduino:renesas_uno` 1.6.0 core); the computer only needs Docker, `make` and `git`. From this folder:

```sh
make build                      # host tests + compile -> dist/garage-<FW_VERSION>.bin
make upload                     # compile and flash over USB (port=/dev/ttyACM0 to change it)
make help                       # every target
```

The image is built on first use. The container runs as you, so `build/` and `dist/` stay yours, and
`make upload` passes the serial port through (`--device`).

With the Arduino IDE, open `firmware/firmware.ino` and select the board "Arduino UNO R4 WiFi".
No extra libraries are needed. Pins and default timings are in `firmware/config.h`.
A newly flashed board needs the first setup (see above); a board already set up keeps its settings.

## Firmware update over the network

No cable needed: from a computer on the same network,

```sh
make update ip=<controller-ip> [version=x.y.z]     # token from $GARAGE_TOKEN, or asked for
```

It runs `tools/update.sh` in the toolchain container on the host's network (so the controller can reach
the file server), which:

1. Runs the host tests and builds the firmware (`tools/build.sh` → `dist/garage-<version>.bin`).
2. Converts it into Arduino's `.ota` format (`tools/make_ota.py`: header, CRC and LZSS compression; the script
   decodes its own output and refuses to continue unless it gives back the exact image).
3. Serves it for a moment from this computer (`python3 -m http.server`, port 8070, `OTA_PORT` to change it).
4. Calls `POST /api/v1/firmware {"url": "http://<this computer>:8070/garage-<version>.ota"}`.
5. Waits until the controller is back running that version.

On the controller (`fwupdate.cpp`), the update is refused while the door moves. The URL is first tried with a
plain HEAD request (5 s limit); then the WiFi module downloads the file, checks its magic number and CRC, and
only then the answer says `flashing`. After that answer the module resets the board into its bootloader,
flashes it and restarts it (about 20 s; `reset_reason` then reads `pin`). Settings are kept.

Errors (HTTP 502): `server_unreachable` (nothing answers at that address: check the computer's firewall allows
incoming TCP 8070), `file_not_found`, `download_failed`, `download_timeout`, `verify_failed`, `storage_error`.

Limits of the WiFi module firmware (checked on the bench with module firmware 0.6.0, and in its sources):
- **There is no rollback.** A firmware that starts but cannot reach the network has to be fixed over USB. Try
  every build on a bench board first.
- **The module's own download hangs the module** (network, web and even the USB serial port, which also goes
  through it) when the server does not answer. That is why the URL is checked first.
- **Uploading the file to the module from the board does not work reliably:** its file write command stops
  listening to the board after any error, until a power cycle. Not used.

## Tests

- `make test` (`test/run.sh`) compiles the door and light logic, the watchdog, the settings storage and the
  JSON readers for the PC and runs them against simulated inputs and a simulated flash.
- `make smoke ip=<ip>` (`test/api_smoke.sh`, token from `$GARAGE_TOKEN`) checks a running device without
  moving the door.
- Watchdog on the bench: `make upload flags=-DWATCHDOG_SELFTEST=1` (main loop hangs 30 s after boot: reset
  about 60 s later) or `flags=-DWATCHDOG_SELFTEST=2` (interrupts stop: reset within 5 s).
  `reset_reason` in `/info` must then read `watchdog`. Never upload these builds to the real installation.

## Layout

```
firmware/
  firmware.ino        setup and main loop
  config.h            pins, default timings, behaviour
  settings.h/.cpp     settings stored in data flash (WiFi, token, name, door timings)
  json.h              small readers for JSON request bodies
  garage.h/.cpp       inputs, door state machine, light timer, relays
  net.h/.cpp          WiFi: home network, setup network, network change with fallback
  http.h/.cpp         HTTP server and API
  web.h               web page
  web_setup.h         setup page (setup mode)
  display.h/.cpp      LED matrix
  watchdog.h/.cpp     hardware watchdog fed from the timer interrupt, reset reason
  fwupdate.h/.cpp     network update: URL check, download and reflash through the WiFi module
tools/
  build.sh            tests + build -> dist/garage-<version>.bin
  make_ota.py         .bin -> .ota (Arduino's OTA format)
  update.sh           network update from a computer on the LAN
test/
  garage_test.cpp     host tests for the logic
  api_smoke.sh        checks against a running device
```
