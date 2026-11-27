"""Device representations."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, StringConstraints

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
