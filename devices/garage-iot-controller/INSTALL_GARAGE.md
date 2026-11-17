# Installing firmware v2 on the garage board

Step-by-step guide for the first installation on the real board (the one in the garage).
Prepared on 2026-11-17. Delete this file once the installation is done and checked.

## Where we are

- Firmware v2 is on the branch `garage-v2` (pushed to GitHub, PR not opened yet).
- The user **has already rewired** the button and the door sensor to the new scheme (2026-11-17):
  each input has a **4.7 kΩ resistor from the pin to +5V** and the contact puts the pin to **GND**.
- **Not measured yet** (step 1 below).

## What to take

- A laptop with this repository, `arduino-cli` and the `arduino:renesas_uno` core (see README, "Build and upload").
- USB cable for the board. The first installation must be over USB: the old firmware cannot update itself.
- A jumper wire (pin 7 to GND) and a phone, for the first setup.
- A multimeter.
- Optional: two 10 kΩ resistors for pins 2 and 3 to GND (see README, "Wiring").

## 1. Check the wiring (multimeter, between each pin and GND, board powered)

| Pin | At rest | Active | If not |
|-----|---------|--------|--------|
| 9 (button) | about 5 V | about 0 V while the button is pressed | |
| 9 (remote control) | about 5 V | about 0 V while the remote is pressed | the remote's relay contact must also go to GND, in parallel with the button |
| 11 (door sensor) | about 5 V with the door open | **below 1 V** with the door closed | if it reads around 3.4 V: the old 10 kΩ series resistor is still on the sensor wire, remove it |

Also check that no resistor from pin 9 or pin 11 to GND is left (the old pull-downs).

## 2. Upload the firmware over USB

```sh
git checkout garage-v2
cd devices/garage-iot-controller
test/run.sh
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi firmware
arduino-cli upload  --fqbn arduino:renesas_uno:unor4wifi -p /dev/ttyACM0 firmware
```

After the upload the board has no settings: it does not use WiFi, but door, button, remote and automatic
light already work. The LED matrix shows `C` while the door is closed and `B` while the button is pressed:
a quick check of step 1.

## 3. First setup

1. Jumper **pin 7 to GND** and press reset. The LED matrix shows `SET`.
2. With the phone, join the open WiFi network `garage-xxxxxx` and open `http://192.168.4.1/`.
3. Name, WiFi network and password, **a new token** (the page can generate one; write it down) and the door
   timings (opening 20 s, close confirmation 40 s). Save.
4. **Remove the jumper** and press Restart. Find the board's address (router, or the LED matrix shows it
   octet by octet after connecting).

## 4. Checks on site

| Check | Expected |
|-------|----------|
| Web page | door state correct, "Last restart" shown |
| `http://<ip>/api/v1/info` | `modem_fw` 0.5.0 or later (needed for network updates; write it down) |
| Push button | door opens; log: "Door opening / Push button or remote · door was closed" |
| Remote control | same as the button |
| Full close | log: "Door closed / Close confirmed by the closed sensor" |
| Open and close from the web | work, with the token |
| A pulse while the door moves | write down whether the door **stops** or **reverses** (the firmware assumes it stops) |
| At night, open | light on for 2 min |
| WiFi signal | `wifi.rssi` in `/api/v1/state`; below -80 dBm expect slow reconnections |

Then update `NOTES.md` (results) and delete this file.

## Going back to the old firmware

The old firmware (branch `main`, `devices/garage-iot-controller/src/`) expects the **old wiring**: contacts to
5V with pull-downs to GND. With the new wiring it would read the button as pressed all the time. To go back:

1. Undo the rewiring (contacts to 5V, 4.7 kΩ to GND, 10 kΩ in series on the sensor wire).
2. Put the real WiFi credentials in `src/wifi_manager.h` (`WIFI_SSID`, `WIFI_PASSWORD`; the file in git has
   placeholders) without committing them.
3. Upload it:

```sh
git checkout main
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi devices/garage-iot-controller/src
arduino-cli upload  --fqbn arduino:renesas_uno:unor4wifi -p /dev/ttyACM0 devices/garage-iot-controller/src
```

Simpler alternative if only the firmware misbehaves: stay on v2 and fix it, the wiring is already the new one.
