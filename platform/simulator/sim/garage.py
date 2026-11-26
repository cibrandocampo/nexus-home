"""The garage controller's logic, ported from devices/garage-iot-controller/firmware/garage.cpp.

The firmware runs `tick()` 100 times a second from a timer interrupt; here `Garage.advance()`
runs the same ticks for the simulated time that has passed (real time times `speed`). Names,
order of checks and side effects follow garage.cpp so the answers match a real board; keep them
in step when the firmware changes.

What the firmware cannot see is modelled in `Opener`: a single-button opener that starts, stops or
reverses the door on each relay pulse, and the closed sensor at the bottom of its travel.
"""

import random
from collections import deque
from dataclasses import dataclass, field

TICK_HZ = 100
LOG_SIZE = 64
DOOR_PULSE_MS = 400
DOOR_PULSE_GAP_MS = 1200
DOOR_SETTLE_MS = 3000
DEBOUNCE_BUTTON_MS = 30
DEBOUNCE_DOOR_MS = 50
DEBOUNCE_NIGHT_MS = 60000
LIGHT_SAMPLE_MS = 1000
NIGHT_HYSTERESIS = 30
LAMP_SETTLE_MS = 10000
LIGHT_MAX_S = 86400


def ticks_of(ms: int) -> int:
    return (ms * TICK_HZ + 999) // 1000


@dataclass
class Settings:
    """What the board stores (settings.h), with the firmware's defaults."""

    name: str = "Garage"
    wifi_ssid: str = "nexus-sim"
    wifi_password: str = "sim-password"  # noqa: S105 - the simulated board's fake network
    token: str = ""
    open_s: int = 20
    close_s: int = 40
    light_s: int = 120
    night_level: int = 700
    display: bool = True


@dataclass
class Input:
    state: bool = False
    count: int = 0


def debounce(inp: Input, raw: bool, ticks: int) -> bool:
    """True when the filtered state changes (garage.cpp `debounce`)."""
    if raw == inp.state:
        inp.count = 0
        return False
    inp.count += 1
    if inp.count < ticks:
        return False
    inp.state = raw
    inp.count = 0
    return True


@dataclass
class Opener:
    """The physical door: position 0 (closed, sensor active) to 1 (fully open).

    Like the real single-button opener, a pulse starts a stopped door (up from closed, down from
    fully open, otherwise the other way from its last movement) and stops a moving one.
    `obstructed` makes a closing door turn back up, as the opener's safety does, so the close is
    never confirmed.
    """

    up_s: float = 16.0
    down_s: float = 19.0
    position: float = 0.0
    motion: int = 0  # +1 up, -1 down, 0 stopped
    last_dir: int = -1
    obstructed: bool = False

    def pulse(self) -> None:
        if self.motion:
            self.last_dir = self.motion
            self.motion = 0
        elif self.position <= 0:
            self.motion = 1
        elif self.position >= 1:
            self.motion = -1
        else:
            self.motion = -self.last_dir

    def step(self, dt: float) -> None:
        if self.motion > 0:
            self.position = min(1.0, self.position + dt / self.up_s)
        elif self.motion < 0:
            if self.obstructed and self.position < 0.5:
                self.motion = 1  # safety reverse: never reaches the sensor
                return
            self.position = max(0.0, self.position - dt / self.down_s)
        if self.motion and self.position in (0.0, 1.0):
            self.last_dir = self.motion
            self.motion = 0

    @property
    def sensor_closed(self) -> bool:
        return self.position <= 0.0


@dataclass
class LogEntry:
    t: int
    event: str
    source: str = "none"
    reason: str = "none"
    value: int = 0


def door_event(door: str) -> str:
    return {
        "closed": "door_closed",
        "opening": "door_opening",
        "open": "door_open",
        "closing": "door_closing",
    }[door]


@dataclass
class Garage:
    settings: Settings = field(default_factory=Settings)
    opener: Opener = field(default_factory=Opener)
    base_light_level: int = 400
    noise: int = 3
    rng: random.Random = field(default_factory=random.Random)

    def __post_init__(self) -> None:
        self.boot()

    # ---- boot (garage.cpp begin + configure) ----

    def boot(self) -> None:
        self.ticks = 0
        self.rev = 0
        self.button_raw = False
        self.button_release_at = 0
        self.button = Input()
        self.closed = Input(state=self.opener.sensor_closed)
        self.door = "closed" if self.closed.state else "open"
        self.door_source = "none"
        self.door_since = 0
        self.door_timer = 0
        self.left_closed = False
        self.close_failed = False
        self.pulse_ticks = 0
        self.gap_ticks = 0
        self.stopped = "none"
        self.queued = 0
        self.queued_src = "none"
        self.light = False
        self.light_timed = False
        self.light_ticks = 0
        self.light_off_at = 0
        self.log: deque[LogEntry] = deque(maxlen=LOG_SIZE)
        self.light_level = self.base_light_level
        self.raw_night = False
        self.next_sample = 0
        self.configure()
        self.night = Input(state=self.raw_night)
        self.record("boot")
        self.record(door_event(self.door), "sensor", "startup")
        self.note("wifi_up")  # net.cpp onConnected: logged with a rev increment

    def configure(self) -> None:
        s = self.settings
        self.open_ticks = s.open_s * TICK_HZ
        self.close_ticks = s.close_s * TICK_HZ
        self.light_def_ticks = s.light_s * TICK_HZ
        self.night_level = s.night_level
        self.decide_night(fresh=True)  # garage.cpp configure: a new level applies at once

    # ---- helpers ----

    @property
    def uptime_s(self) -> int:
        return self.ticks // TICK_HZ

    def record(
        self, event: str, source: str = "none", reason: str = "none", value: int = 0
    ) -> None:
        self.log.append(LogEntry(self.uptime_s, event, source, reason, value))

    def note(self, event: str, source: str = "none") -> None:
        self.record(event, source)
        self.rev += 1

    def set_door(self, door: str, timer: int, why: str, log: bool = True) -> None:
        self.door_timer = timer
        if why != "stopped":
            self.stopped = "none"
        if (
            self.door == door
        ):  # as garage.cpp setDoor; no path of the state machine lands here today
            return
        self.door = door
        self.door_since = self.ticks
        if door == "closed":
            self.close_failed = False
        self.rev += 1
        if log:
            self.record(door_event(door), self.door_source, why)

    def set_light(self, on: bool, ticks: int, src: str) -> None:
        if self.light and not on:
            self.light_off_at = self.ticks
        self.light = on
        self.light_timed = on and ticks > 0
        self.light_ticks = ticks if on else 0
        self.rev += 1
        self.record("light_on" if on else "light_off", src, "none", ticks // TICK_HZ if on else 0)

    def auto_light(self) -> None:
        if not self.night.state:
            return
        if self.light and not self.light_timed:
            return
        t = self.light_def_ticks
        self.set_light(True, max(self.light_ticks, t), "auto")

    def start_opening(self, src: str, why: str) -> None:
        self.door_source = src
        self.left_closed = not self.closed.state
        self.set_door("opening", self.open_ticks, why)
        self.auto_light()

    def pulse(self, src: str) -> bool:
        if self.pulse_ticks or self.gap_ticks:
            return False
        self.opener.pulse()
        self.pulse_ticks = ticks_of(DOOR_PULSE_MS)
        self.gap_ticks = ticks_of(DOOR_PULSE_GAP_MS)
        self.close_failed = False
        self.rev += 1
        if self.door == "closed":
            self.start_opening(src, "command")
        elif self.door == "open":
            if self.stopped == "down":
                self.start_opening(src, "command")
            else:
                self.door_source = src
                self.set_door("closing", self.close_ticks, "command")
        else:
            was = "up" if self.door == "opening" else "down"
            self.door_source = src
            self.set_door("closed" if self.closed.state else "open", 0, "stopped")
            self.stopped = was if self.door == "open" else "none"
        return True

    def step_door(self) -> None:
        closed = self.closed.state
        if self.door == "closed":
            if not closed:
                self.start_opening("sensor", "sensor_released")
        elif self.door == "opening":
            if self.ticks - self.door_since < ticks_of(DOOR_SETTLE_MS):
                pass
            elif not closed:
                self.left_closed = True
            elif self.left_closed:
                self.set_door("closed", 0, "came_back")
                return
            self.door_timer -= 1
            if self.door_timer == 0:
                self.set_door(
                    "closed" if closed else "open", 0, "no_movement" if closed else "travel_end"
                )
        elif self.door == "open":
            if closed:
                self.door_source = "sensor"
                self.set_door("closed", 0, "sensor_closed")
        elif self.door == "closing":
            if closed:
                self.set_door("closed", 0, "sensor_closed")
            else:
                self.door_timer -= 1
                if self.door_timer == 0:
                    self.set_door("open", 0, "none", log=False)
                    self.close_failed = True
                    self.record(
                        "close_failed", self.door_source, "none", self.close_ticks // TICK_HZ
                    )

    def decide_night(self, fresh: bool = False) -> None:
        level = self.night_level
        day_below = level - NIGHT_HYSTERESIS if level > NIGHT_HYSTERESIS else 0
        if self.light_level >= level:
            self.raw_night = True
        elif fresh or self.light_level < day_below:
            self.raw_night = False

    def sample_light_level(self) -> None:
        jitter = self.rng.randint(-self.noise, self.noise) if self.noise else 0
        self.light_level = max(0, min(1023, self.base_light_level + jitter))
        self.decide_night()

    # ---- one 10 ms step (garage.cpp tick) ----

    def tick(self) -> None:
        self.ticks += 1
        self.opener.step(1 / TICK_HZ)
        if self.button_raw and self.ticks >= self.button_release_at:
            self.button_raw = False
        if self.ticks >= self.next_sample:  # the main loop samples A0 once per second
            self.next_sample = self.ticks + ticks_of(LIGHT_SAMPLE_MS)
            self.sample_light_level()
        if debounce(self.button, self.button_raw, ticks_of(DEBOUNCE_BUTTON_MS)):
            self.rev += 1
            if self.button.state:
                self.queued = 0
            if self.button.state and not self.pulse("button"):
                self.record("button_ignored", "button", "too_soon")
        if debounce(self.closed, self.opener.sensor_closed, ticks_of(DEBOUNCE_DOOR_MS)):
            self.rev += 1
        if self.light or self.ticks - self.light_off_at < ticks_of(LAMP_SETTLE_MS):
            self.night.count = 0
        elif debounce(self.night, self.raw_night, ticks_of(DEBOUNCE_NIGHT_MS)):
            self.rev += 1
            self.record("night" if self.night.state else "day")
        if self.pulse_ticks:
            self.pulse_ticks -= 1
            if self.pulse_ticks == 0:
                self.rev += 1
        if self.gap_ticks:
            self.gap_ticks -= 1
        if self.queued and not self.pulse_ticks and not self.gap_ticks:
            self.queued -= 1
            self.pulse(self.queued_src)
        self.step_door()
        if self.light_timed:
            self.light_ticks -= 1
            if self.light_ticks == 0:
                self.set_light(False, 0, "auto")

    def advance(self, ticks: int) -> None:
        for _ in range(ticks):
            self.tick()

    # ---- commands (garage.cpp doorOpen … lightToggle): "ok", "noop" or "busy" ----

    def _reverse_then(self, src: str) -> str:
        if self.queued or not self.pulse(src):
            return "busy"
        self.queued = 2
        self.queued_src = src
        return "ok"

    def _pulse_cmd(self, src: str) -> str:
        return "ok" if self.pulse(src) else "busy"

    def door_open(self, src: str = "api") -> str:
        if self.queued:
            return "busy"
        if self.door == "closed":
            return self._pulse_cmd(src)
        if self.door == "closing":
            return "busy"
        if self.door == "open":
            if self.stopped == "up":
                return self._reverse_then(src)
            if self.stopped == "down":
                return self._pulse_cmd(src)
        return "noop"

    def door_close(self, src: str = "api") -> str:
        if self.queued:
            return "busy"
        if self.door == "open":
            return self._reverse_then(src) if self.stopped == "down" else self._pulse_cmd(src)
        if self.door == "opening":
            return "busy"
        return "noop"

    def door_stop(self, src: str = "api") -> str:
        cancelled = bool(self.queued)
        self.queued = 0
        if self.door not in ("opening", "closing"):
            return "ok" if cancelled else "noop"
        return self._pulse_cmd(src)

    def door_toggle(self, src: str = "api") -> str:
        self.queued = 0
        return self._pulse_cmd(src)

    def light_on(self, seconds: int) -> str:
        if seconds == 0 and self.light and not self.light_timed:
            return "noop"
        self.set_light(True, seconds * TICK_HZ, "api")
        return "ok"

    def light_off(self) -> str:
        if not self.light:
            return "noop"
        self.set_light(False, 0, "api")
        return "ok"

    def light_toggle(self) -> None:
        if self.light:
            self.set_light(False, 0, "api")
        else:
            self.set_light(True, self.light_def_ticks, "api")

    def press_button(self) -> None:
        """The push button or the remote: held for 200 ms."""
        self.button_raw = True
        self.button_release_at = self.ticks + ticks_of(200)

    @property
    def busy(self) -> bool:
        """Restart and firmware update are refused while this holds (http.cpp doorBusy)."""
        return self.door in ("opening", "closing") or self.pulse_ticks > 0

    # ---- JSON views (http.cpp) ----

    def state_json(self, ip: str, rssi: int) -> dict:
        moving = self.door in ("opening", "closing")
        return {
            "rev": self.rev,
            "uptime_s": self.uptime_s,
            "door": {
                "state": self.door,
                "moving": moving,
                "sensor_closed": self.closed.state,
                "close_failed": self.close_failed,
                "stopped": self.stopped,
                "since_s": (self.ticks - self.door_since) // TICK_HZ,
                "last_source": self.door_source,
            },
            "light": {
                "state": "on" if self.light else "off",
                "timed": self.light_timed,
                "remaining_s": (self.light_ticks + TICK_HZ - 1) // TICK_HZ,
            },
            "night": self.night.state,
            "light_level": self.light_level,
            "button": self.button.state,
            "display": self.settings.display,
            "wifi": {"ip": ip, "rssi": rssi},
        }

    def log_json(self) -> dict:
        return {
            "uptime_s": self.uptime_s,
            "events": [
                {
                    "t": e.t,
                    "event": e.event,
                    "source": e.source,
                    "reason": e.reason,
                    "value": e.value,
                }
                for e in reversed(self.log)
            ],
        }
