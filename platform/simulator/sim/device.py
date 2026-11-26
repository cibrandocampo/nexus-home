"""A simulated garage board: the logic (garage.py) on a clock, plus what http.cpp and
settings.cpp add around it (identity, stored settings and their validation, restart).
Framework-free so tests can drive it directly; app.py puts HTTP in front of it."""

import hashlib
import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from sim.garage import LIGHT_MAX_S, TICK_HZ, Garage, Settings

MODEL = "Garage IoT Controller (UNO R4 WiFi)"
ENTITIES = [
    {
        "id": "door",
        "type": "cover",
        "device_class": "garage",
        "state": "door.state",
        "commands": ["open", "close", "stop", "toggle"],
    },
    {"id": "light", "type": "light", "state": "light.state", "commands": ["on", "off", "toggle"]},
    {
        "id": "door_problem",
        "type": "binary_sensor",
        "device_class": "problem",
        "state": "door.close_failed",
    },
    {"id": "night", "type": "binary_sensor", "state": "night"},
    {"id": "light_level", "type": "sensor", "state": "light_level"},
    {
        "id": "rssi",
        "type": "sensor",
        "device_class": "signal_strength",
        "unit": "dBm",
        "state": "wifi.rssi",
    },
]

# settings.h limits and field sizes (characters, terminator excluded).
NAME_MAX, SSID_MAX, PASSWORD_MAX, TOKEN_MAX = 32, 32, 63, 64
TOKEN_MIN = 8
LIMITS = {
    "open_s": (5, 100, "invalid_open_time"),
    "close_s": (10, 100, "invalid_close_time"),
    "light_s": (10, 600, "invalid_light_time"),
    "night_level": (1, 1023, "invalid_night_level"),
}
MESSAGES = {
    "too_long": "A text field is too long",
    "invalid_name": "Name must not be empty",
    "invalid_ssid": "WiFi network must not be empty",
    "invalid_password": "WiFi password must be empty or at least 8 characters",
    "invalid_token": "Token must be 8 to 64 characters, no spaces",
    "invalid_open_time": "Opening time must be 5 to 100 seconds",
    "invalid_close_time": "Close confirmation time must be 10 to 100 seconds",
    "invalid_light_time": "Light time must be 10 to 600 seconds",
    "invalid_night_level": "Night level must be 1 to 1023",
    "invalid_display": "display must be true or false",
    "invalid_json": "Malformed field in the request body",
}


class DeviceError(Exception):
    """An error answer: status, code and message, as http.cpp respondError."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(code)
        self.status, self.code, self.message = status, code, message


def _is_int(v: object) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def apply_fields(payload: dict, current: Settings) -> tuple[Settings, bool]:
    """http.cpp applyFields + settings.cpp validate: the new settings and whether the WiFi changed.

    The firmware's JSON reader rejects a string longer than its field with that field's code, and a
    number that is not a non-negative integer with the number's code, before validate() runs.
    """
    d = Settings(**vars(current))

    def text(key: str, size: int, code: str) -> str | None:
        if key not in payload:
            return None
        v = payload[key]
        if not isinstance(v, str) or len(v) > size or any(ord(c) < 0x20 for c in v):
            raise DeviceError(400, code, MESSAGES[code])
        return v

    if (v := text("name", NAME_MAX, "invalid_name")) is not None:
        d.name = v
    if (v := text("token", TOKEN_MAX, "invalid_token")) is not None:
        d.token = v
    for key, (_, _, code) in LIMITS.items():
        if key in payload:
            v = payload[key]
            if not _is_int(v) or v < 0 or v > 0xFFFF:
                raise DeviceError(400, code, MESSAGES[code])
            setattr(d, key, v)
    if "display" in payload:
        if not isinstance(payload["display"], bool):
            raise DeviceError(400, "invalid_display", MESSAGES["invalid_display"])
        d.display = payload["display"]
    ssid = text("wifi_ssid", SSID_MAX, "invalid_ssid")
    password = text("wifi_password", PASSWORD_MAX, "invalid_password")
    wifi_changed = False
    if ssid is not None and ssid != d.wifi_ssid:
        d.wifi_ssid, wifi_changed = ssid, True
    if password is not None and (
        password or wifi_changed
    ):  # empty keeps it, unless the network changed
        if password != d.wifi_password:
            wifi_changed = True
        d.wifi_password = password
    if not d.wifi_ssid:
        raise DeviceError(400, "invalid_ssid", MESSAGES["invalid_ssid"])
    if not d.token:
        raise DeviceError(400, "invalid_token", MESSAGES["invalid_token"])
    if err := validate(d):
        raise DeviceError(400, err, MESSAGES[err])
    return d, wifi_changed


def validate(d: Settings) -> str | None:
    """settings.cpp validate (length checks already done by apply_fields)."""
    if not d.name:
        return "invalid_name"
    if d.wifi_ssid and 0 < len(d.wifi_password) < 8:
        return "invalid_password"
    if d.token and (len(d.token) < TOKEN_MIN or any(c <= " " or c > "~" for c in d.token)):
        return "invalid_token"
    for key, (low, high, code) in LIMITS.items():
        if not low <= getattr(d, key) <= high:
            return code
    return None


@dataclass
class Identity:
    id: str
    version: str = "2.0.5"
    modem_fw: str = "0.6.0"
    ip: str = "127.0.0.1"

    @property
    def mac(self) -> str:
        digest = hashlib.sha256(self.id.encode()).digest()
        return ":".join(f"{b:02X}" for b in (b"\x02" + digest[:5]))


class Device:
    def __init__(
        self,
        identity: Identity,
        settings: Settings | None = None,
        speed: float = 1.0,
        restart_s: float = 2.0,
        now: Callable[[], float] = time.monotonic,
        rng: random.Random | None = None,
    ):
        self.identity = identity
        self.speed = speed
        self.restart_s = restart_s
        self.now = now
        self.rng = rng or random.Random()
        self.garage = Garage(settings=settings or Settings(), rng=self.rng)
        self.reset_reason = "power"
        self.last = now()
        self.carry = 0.0
        self.down_until = 0.0  # not answering (restarting, or the offline hook) until this time
        self.reboot_at: float | None = None
        self.fail_next_save = False

    # ---- clock ----

    def sync(self) -> None:
        """Runs the ticks for the simulated time since the last call; reboots when due."""
        t = self.now()
        if self.reboot_at is not None and t >= self.reboot_at:
            self.advance_to(self.reboot_at)
            self.reboot_at = None
            self.reset_reason = "software"
            self.garage.boot()
        self.advance_to(t)

    def advance_to(self, t: float) -> None:
        elapsed = max(0.0, t - self.last) * self.speed * TICK_HZ + self.carry
        ticks = int(elapsed)
        self.carry = elapsed - ticks
        self.last = t
        self.garage.advance(ticks)

    def down_for(self) -> float:
        """Seconds the board stays silent (0 when it answers)."""
        return max(0.0, self.down_until - self.now())

    # ---- views ----

    @property
    def settings(self) -> Settings:
        return self.garage.settings

    def info(self) -> dict:
        i = self.identity
        return {
            "id": i.id,
            "name": self.settings.name,
            "mode": "normal",
            "manufacturer": "nexusHome",
            "model": MODEL,
            "sw_version": i.version,
            "modem_fw": i.modem_fw,
            "reset_reason": self.reset_reason,
            "api": "v1",
            "mac": i.mac,
            "hostname": i.id,
            "auth": bool(self.settings.token),
            "entities": ENTITIES,
        }

    def state(self) -> dict:
        return self.garage.state_json(self.identity.ip, -58 + self.rng.randint(-3, 3))

    def settings_json(self) -> dict:
        s = self.settings
        return {
            "name": s.name,
            "wifi_ssid": s.wifi_ssid,
            "wifi_password_set": bool(s.wifi_password),
            "token_set": bool(s.token),
            "open_s": s.open_s,
            "close_s": s.close_s,
            "light_s": s.light_s,
            "night_level": s.night_level,
            "display": s.display,
            "stored": True,
            "wifi_trying": False,
        }

    def authorized(self, header: str | None) -> bool:
        token = self.settings.token
        if not token:
            return True
        return bool(header) and header[:7].lower() == "bearer " and header[7:] == token

    # ---- actions ----

    def command(self, path: str, query_duration: str | None, payload: dict) -> dict:
        g = self.garage
        door = {
            "door/open": g.door_open,
            "door/close": g.door_close,
            "door/stop": g.door_stop,
            "door/toggle": g.door_toggle,
        }
        if path in door:
            return self._result(door[path]())
        if path == "light/on":
            seconds = self._duration(query_duration, payload)
            return self._result(g.light_on(seconds))
        if path == "light/off":
            return self._result(g.light_off())
        if path == "light/toggle":
            g.light_toggle()
            return self._result("ok")
        raise DeviceError(404, "not_found", "Unknown command")

    def _duration(self, query: str | None, payload: dict) -> int:
        bad = DeviceError(400, "invalid_duration", "duration must be 0..86400 seconds")
        if query is not None:
            digits = ""
            for c in query:
                if not c.isdigit():
                    break
                digits += c
            if not digits or int(digits) > LIGHT_MAX_S:
                raise bad
            return int(digits)
        if "duration" in payload:
            v = payload["duration"]
            if not _is_int(v) or v < 0 or v > LIGHT_MAX_S:
                raise bad
            return v
        return self.garage.light_def_ticks // TICK_HZ

    def _result(self, r: str) -> dict:
        if r == "busy":
            raise DeviceError(409, "door_busy", "Door is moving or was just triggered, retry later")
        return {"result": r, "state": self.state()}

    def change_settings(self, payload: dict) -> dict:
        old = self.settings
        new, wifi_changed = apply_fields(payload, old)
        keep = Settings(**vars(new))
        keep.wifi_ssid, keep.wifi_password = old.wifi_ssid, old.wifi_password
        if keep != old:
            if self.fail_next_save:
                self.fail_next_save = False
                self.garage.note("settings_save_failed", "api")
                raise DeviceError(500, "save_failed", "Could not write the settings to flash")
            self.garage.settings = keep
            self.garage.configure()
            self.garage.note("settings_changed", "api")
        if wifi_changed:
            # Not simulated: the board would try the new network for up to 60 s. Here it "connects".
            self.garage.settings.wifi_ssid = new.wifi_ssid
            self.garage.settings.wifi_password = new.wifi_password
            self.garage.note("wifi_changed")
            return {"result": "testing_wifi", "settings": self.settings_json()}
        return {"result": "ok", "settings": self.settings_json()}

    def restart(self) -> dict:
        if self.garage.busy:
            raise DeviceError(409, "door_busy", "Door is moving, restart refused")
        self.reboot_at = self.now() + 0.3
        self.down_until = self.now() + self.restart_s
        return {"result": "restarting"}

    # ---- test hooks ----

    def go_offline(self, seconds: float) -> None:
        self.down_until = self.now() + seconds

    def power_cycle(self) -> None:
        self.reset_reason = "power"
        self.garage.boot()
