"""Device representations."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from app.devices.scan import parse_range

# An IPv4 address or a hostname, with an optional port (the simulators in the dev stack).
Host = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=253,
        pattern=r"^[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?(?::\d{1,5})?$",
    ),
]
# The boards accept 8 to 64 printable ASCII characters, no spaces.
DeviceToken = Annotated[str, StringConstraints(min_length=8, max_length=64, pattern=r"^[!-~]+$")]


class DeviceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: Host
    token: DeviceToken | None = None


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_id: str
    type: str
    name: str
    model: str
    host: str
    has_token: bool
    sw_version: str
    modem_fw: str
    mode: str
    reset_reason: str
    mac: str
    entities: list[dict[str, Any]]
    state: dict[str, Any] | None
    rev: int | None
    online: bool
    last_seen_at: datetime | None
    uptime_s: int | None
    created_at: datetime


class DevicePage(BaseModel):
    items: list[DeviceOut]
    total: int
    page: int
    size: int


class ScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # None: the configured SCAN_RANGES. Each item an IPv4 CIDR or address (checked by the scan).
    ranges: list[Annotated[str, StringConstraints(max_length=43)]] | None = Field(
        default=None, min_length=1, max_length=16
    )

    @field_validator("ranges")
    @classmethod
    def _cidrs(cls, value: list[str] | None) -> list[str] | None:
        if value is not None:
            for item in value:
                parse_range(item)  # ValueError → 422
        return value


class ScanResult(BaseModel):
    device_id: str
    name: str
    model: str
    sw_version: str
    host: str
    auth: bool
    registered: bool
    id: int | None


class ScanOut(BaseModel):
    items: list[ScanResult]
    scanned: int
    duration_s: float


class ScanRanges(BaseModel):
    ranges: list[str]


class Ref(BaseModel):
    id: int
    name: str | None


class EventOut(BaseModel):
    id: int
    at: datetime
    event: str
    source: str
    reason: str
    value: int
    device: Ref
    # Who sent the platform command that caused it; null for the button, the sensor, the board…
    user: Ref | None


class EventPage(BaseModel):
    items: list[EventOut]
    total: int
    page: int
    size: int


class CommandIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # light/on only: seconds, 0 = no timer (the board's range).
    duration: int | None = Field(default=None, ge=0, le=86_400, strict=True)


class CommandOut(BaseModel):
    result: str  # ok, noop
    state: dict[str, Any] | None
