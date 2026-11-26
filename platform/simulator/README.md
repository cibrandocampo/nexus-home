# Garage board simulator

A stand-in for the garage controller (`devices/garage-iot-controller`) that speaks its `/api/v1` on port
80, for the platform's tests, dev stack and end-to-end suite. Development and tests only: it is never
deployed.

- `sim/garage.py` ports the firmware's logic (`firmware/garage.cpp`): door state machine, stopped part
  way and the three-pulse reversal, close confirmation and `close_failed`, pulse gap, auto light at night,
  night debounce and the lamp settle time, event log of 64 entries, `rev`. A physical model of the door
  (`Opener`: single-button opener, closed sensor at the bottom) stands in for the real one.
- `sim/device.py` adds what `http.cpp` and `settings.cpp` do: identity and entities (`/info`), stored
  settings with the same validation and error codes, token, restart.
- `sim/app.py` routes like `http.cpp`: same paths, methods, order of checks (method, origin, token) and
  error envelope.

Keep it in step with the firmware: `tests/test_contract.py` reads the garage README (JSON examples,
event and reason names, error table) and `firmware/http.cpp` (the keys of every JSON answer) and fails
when the simulator drifts. The Platform workflow runs when either file changes.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `SIM_ID` | `garage-5e1a00` | Device id (`garage-<6 hex>`), also its hostname |
| `SIM_NAME` | `Garage` | Stored name |
| `SIM_TOKEN` | empty | Access token; empty = no token, as a new board |
| `SIM_VERSION` | `2.0.5` | `sw_version` |
| `SIM_SPEED` | `1` | Simulated seconds per real second |
| `SIM_LIGHT_LEVEL` | `400` | Light sensor level (higher = darker; night from 700) |
| `SIM_IP` | the container's address | `wifi.ip` in the state |
| `SIM_RESTART_S` | `2` | Real seconds it stays silent after `/restart` |
| `SIM_HOOKS` | `1` | `0` turns the test hooks off |

## Test hooks (not on real boards)

`POST` to these (a real board answers 404):

| Path | Body | Does |
|---|---|---|
| `/sim/button` | — | Presses the push button (or the remote) for 200 ms |
| `/sim/door` | `{"position": 0..1}` | Moves the door by hand (0 = closed) |
| `/sim/obstruct` | `{"on": true}` | A closing door turns back before the sensor: `close_failed` |
| `/sim/light_level` | `{"level": 900}` | Sets the light sensor level |
| `/sim/offline` | `{"seconds": 10}` | Stops answering for that long (requests hang, as an unreachable board) |
| `/sim/fail_next_save` | — | The next settings change answers 500 `save_failed` |
| `/sim/power_cycle` | — | Restarts now with `reset_reason` `power` |

`GET /sim/status` shows the physical door (position, motion, obstruction), the uptime and the speed.

## Request bodies, as the board reads them

The board does not parse JSON: it finds `"key":` in the raw body and reads the value there
(`firmware/json.h`, ported in `sim/fwjson.py`). What a client must know:

- Strings are counted in **bytes** (a name holds 32: 16 "ñ" fit, 17 do not). Raw UTF-8 passes; a `\u`
  escape above 0x7F is refused, so send non-ASCII text as raw UTF-8, never escaped (Python's
  `json.dumps` escapes by default: use `ensure_ascii=False`). Escaped control characters (`\n`) are
  accepted, raw ones are not.
- Numbers are plain digits: `30.0` is refused in the settings; a light `duration` is read up to its
  first non-digit (`30.5` is 30 s).
- A body that is not JSON has no fields: the settings answer 200 `ok` with nothing changed.

## Not simulated

- Setup mode (`/setup`) and the web page (a placeholder).
- A WiFi network change always works: the board answers `testing_wifi` (old network, `wifi_trying`),
  stays silent for `SIM_RESTART_S` and comes back on the new one (`wifi_up`, `wifi_changed`); a network
  that fails (`wifi_change_failed` after 60 s on a board) is not simulated.
- Firmware updates: `/firmware` answers 501 `not_simulated` (platform phase 3 adds them).
- The transport limits of the board's server: requests over 1 KB (413 `too_large`), one connection at a
  time with `Connection: close`, and its 1.5 s read timeout. A real board is slower and serial: a
  client must not rely on the simulator's concurrency or speed.
- The MAC's first three bytes (the module maker's on a board; `02:00:00` here). The last three are the
  id, as on a board.

One difference to keep in mind when writing tests: after `/sim/power_cycle` with the door part way,
the simulated opener still remembers which way it last moved, as a real opener does, but the board
starts with no memory of it (`stopped: none`). A `close` can then drive the door up and end in
`close_failed`, exactly as on the real installation after a power cut.

## Commands (from `platform/`)

```sh
make test-simulator      # tests with coverage, contract included
make lint-simulator      # ruff
make format-simulator
```

In the dev stack: `sim-garage-a` (`garage-5e1a0a`) and `sim-garage-b` (`garage-5e1a0b`), tokens from
`SIM_GARAGE_A_TOKEN` / `SIM_GARAGE_B_TOKEN`, reachable from the backend as `http://sim-garage-a/`.
