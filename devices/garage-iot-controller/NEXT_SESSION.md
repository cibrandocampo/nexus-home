# Next session: update server, then the real installation

Hand-off updated on 2026-11-17. Read [NOTES.md](NOTES.md) first for the full context and decisions.
Delete this file once the steps below are done.

## Where we are

- Firmware v2 (2.0.0) runs on the bench board: a new Arduino UNO R4 WiFi on `/dev/ttyACM0`, nothing wired
  to it except an LED/multimeter on pin 3, at `http://10.1.3.114/` (DHCP, may change). Door commands can be
  tested freely. It is set up (WiFi, token) through setup mode; ask the user for the token.
- Updates: over the network with `tools/update.sh 10.1.3.114` (preferred), or over USB (`arduino-cli upload`).
  `test/run.sh` passes.
- Bench tests with jumpers mostly done (NOTES, "Board test results"); left: one event per touch with the
  real button, LED matrix, WiFi loss.
- Committed on the local branch `garage-v2` (2026-11-17), not pushed.
- `firmware/secrets.h` is no longer used; the git-ignored file may still exist with old credentials: do not
  print it.

## Step 1: bench tests with jumpers

Wiring on the bare board:

| Pin | Function | Idle | Active |
|-----|----------|------|--------|
| 9 | Button | leave open | touch to **GND** = pressed |
| 11 | Door sensor | leave open = not closed | jumper to **GND** = door closed |
| 12 | Light sensor | jumper to GND = day (it floats if left open) | jumper to **5V** = night |
| 6 | LED matrix | leave open = on | jumper to GND = matrix off |

Pins 2 (light relay) and 3 (door relay) are outputs: measure them, never jumper them to 5V or GND.

Start with pin 11 to GND and pin 12 to GND (door closed, day). Follow along with
`curl http://<ip>/api/v1/log` or the "Recent activity" list on the web page.

| Check | Action | Expected |
|-------|--------|----------|
| Button | touch pin 9 to GND | one `button` event and `opening`; pin 3 pulses for 0.4 s |
| No double presses | several touches, more than 1.2 s apart | exactly one event per touch |
| Open, sensor never released | press, leave pin 11 on GND | `closed` again after 20 s |
| Open | press, remove the jumper from pin 11 | `open` after 20 s |
| Close | press, put pin 11 back to GND | `closing`, then `closed` at once |
| Slow close | press with the door open, put pin 11 to GND after 30 s | `closing`, then `closed`, no alert |
| Failed close | press with the door open, leave pin 11 open | `closing`, then `open` after 40 s, red alert on the web, `close_failed` in the log |
| Alert cleared | after a failed close, put pin 11 to GND | `closed`, the alert disappears |
| Moved without the board | remove the jumper from pin 11 without pressing | `opening`, source `sensor` |
| Stop | press while moving (more than 1.2 s after the last pulse) | stops: `open` or `closed` by the sensor |
| Busy | `door/open` then `door/close` right away, over the API | 409 `door_busy` |
| Auto light | pin 12 to 5V, wait 2 s, open | light on for 120 s, source `auto` |
| Held at boot | hold pin 9 on GND and press reset | no relay pulse |
| Reset reason | press the reset button | "Last restart: reset button" on the web (`reset_reason: pin`) |
| LED matrix | look at the board | letters `N` `C` `B` and bars as described in README |
| WiFi loss | switch the router/AP off for a minute | the button still pulses the relay; `wifi_down` / `wifi_up` in the log |

## Step 2: next features

Done and tested on the bench board (2026-11-17): watchdog; stored settings with the WiFi setup mode and the
restart button ([PLAN_SETTINGS.md](PLAN_SETTINGS.md)), including the WiFi change with fallback; network
firmware update with `tools/update.sh` (README, "Firmware update over the network"; NOTES, "OTA").

Next: the update server in a Docker container on the user's server (LAN, plain HTTP), which will later be the
Home Assistant gateway. Ask the user for the server details (Docker / compose, address).

## Step 3: real installation

1. Rewire the inputs (see "Wiring" in README): the second wire of the button and of the door sensor
   goes to GND instead of 5V, and the 4.7 kΩ pull-downs on pins 9 and 11 are removed or moved to 5V.
2. Read `modem_fw` from `/api/v1/info` on that board (OTA needs 0.5.0 or later).
3. Confirm what a pulse does while the door is moving (stop or reverse).
4. Add 10 kΩ from pins 2 and 3 to GND unless the relay module already has them (README, "Wiring").
5. First setup with the pin 7 jumper; use a new token (the bench token was shared in a chat).

## Step 4: push and PR

The work is on the local branch `garage-v2`. Push it and open a PR only when the user asks for it.
