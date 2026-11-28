"""Device types: what the platform knows about each board type beyond its `/info` entities.

The type is the device id prefix (`garage-3562d4` → `garage`). An unknown type is still stored,
polled and shown through its generic entities; it just has no settings form.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class IntField:
    name: str
    min: int
    max: int


@dataclass(frozen=True)
class Driver:
    type: str
    label: str
    # Settings the platform edits (GET/POST /settings): never WiFi, never the token.
    text_fields: dict[str, int] = field(default_factory=dict)  # name → max UTF-8 bytes
    int_fields: tuple[IntField, ...] = ()
    bool_fields: tuple[str, ...] = ()
    firmware_prefix: str = ""  # release asset name prefix (phase 3)

    @property
    def settings_fields(self) -> tuple[str, ...]:
        return (
            *self.text_fields,
            *(f.name for f in self.int_fields),
            *self.bool_fields,
        )


# Ranges from devices/garage-iot-controller/firmware/settings.h.
GARAGE = Driver(
    type="garage",
    label="Garage",
    text_fields={"name": 32},
    int_fields=(
        IntField("open_s", 5, 100),
        IntField("close_s", 10, 100),
        IntField("light_s", 10, 600),
        IntField("night_level", 1, 1023),
    ),
    bool_fields=("display",),
    firmware_prefix="garage-",
)

DRIVERS = {d.type: d for d in (GARAGE,)}


def driver_for(device_type: str) -> Driver | None:
    return DRIVERS.get(device_type)


def device_type(device_id: str) -> str:
    return device_id.split("-", 1)[0]
