# Next session

Hand-off updated on 2026-11-19. Read [NOTES.md](NOTES.md) first for the full context and decisions.
The user wants answers in Spanish (code and repository text in English).

## Where we are

- **Garage board** (`garage-3562d4`, `http://10.1.3.103/`): in production with the new wiring. Runs 2.0.3;
  2.0.4 (door stopped part way, see README "Stopped part way") is committed and about to be installed and
  checked on the real door: stop a close, then Push button (must open), Close (three pulses), Open (three
  pulses). Someone must watch the door. Installation checks: NOTES, "Garage installation".
- **Bench board** (`garage-33ad84`, `/dev/ttyACM0`, `http://10.1.3.114/`, DHCP): nothing wired, A0 floating
  (~200). Door commands can be tested freely. Runs 2.0.4.
- Updates: `tools/update.sh <ip>` over the network (token from `$GARAGE_TOKEN` or asked), or USB for the bench.
- **Light level logger**: `build/lightlog/log_light.sh` (detached, every 30 s) writes `build/lightlog/light.csv`.
  In a few days: read the midday level with the door closed and adjust the night level (700 now) from the web.
  Stop the logger afterwards.
- `firmware/secrets.h` is no longer used; the git-ignored file may still exist with old credentials: do not
  print it.

## Next

1. Check 2.0.4 on the garage door (above).
2. Night threshold from the logged data (above).
3. WiFi network picker (NOTES, To do 11).
4. Update server in a Docker container on the user's server (LAN, plain HTTP), later the Home Assistant
   gateway. Ask the user for the server details.

## Bench tests with jumpers (still open: WiFi loss, one event per touch with a real button)

| Pin | Function | Idle | Active |
|-----|----------|------|--------|
| 9 | Button | leave open | touch to **GND** = pressed |
| 11 | Door sensor | leave open = not closed | jumper to **GND** = door closed |
| A0 | Light level | jumper to GND = 0, bright (it floats if left open) | jumper to **5V** = 1023, dark |

Pins 2 (light relay) and 3 (door relay) are outputs: measure them, never jumper them to 5V or GND.

| Check | Action | Expected |
|-------|--------|----------|
| No double presses | several touches, more than 1.2 s apart | exactly one event per touch |
| WiFi loss | switch the router/AP off for a minute | the button still pulses the relay; `wifi_down` / `wifi_up` in the log |
