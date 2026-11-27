"""Registered devices."""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The board's own id from /info (`garage-3562d4`): unique, survives an IP change.
    device_id: Mapped[str] = mapped_column(String(64), unique=True)
    type: Mapped[str] = mapped_column(String(32))  # the id prefix (`garage`): selects the driver
    name: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128), default="")
    host: Mapped[str] = mapped_column(String(253))  # IP or hostname, optional :port
    # Fernet token (devices/crypto.py); null for a board registered without one.
    token_encrypted: Mapped[str | None] = mapped_column(String(512))
    sw_version: Mapped[str] = mapped_column(String(32), default="")
    modem_fw: Mapped[str] = mapped_column(String(32), default="")
    mode: Mapped[str] = mapped_column(String(16), default="")
    reset_reason: Mapped[str] = mapped_column(String(32), default="")
    mac: Mapped[str] = mapped_column(String(17), default="")
    entities: Mapped[list] = mapped_column(JSONB, default=list)
    state: Mapped[dict | None] = mapped_column(JSONB)
    rev: Mapped[int | None]
    online: Mapped[bool] = mapped_column(default=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uptime_s: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    @property
    def has_token(self) -> bool:
        return self.token_encrypted is not None


class DeviceBoot(Base):
    """One run of a board between two restarts: its log times (`t`) count from `started_at`."""

    __tablename__ = "device_boots"

    id: Mapped[int] = mapped_column(primary_key=True)
    device_pk: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"), index=True)
    # Estimated as read time - uptime; refreshed on every read (the board's clock drifts a little).
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_uptime_s: Mapped[int]
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class DeviceEvent(Base):
    """An entry of a board's event log, stored once with its absolute time."""

    __tablename__ = "device_events"
    __table_args__ = (Index("ix_device_events_device_pk_at", "device_pk", "at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    device_pk: Mapped[int] = mapped_column(ForeignKey("devices.id", ondelete="CASCADE"))
    boot_id: Mapped[int] = mapped_column(
        ForeignKey("device_boots.id", ondelete="CASCADE"), index=True
    )
    t: Mapped[int]  # seconds since the boot, as the board logged it
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    event: Mapped[str] = mapped_column(String(32))
    source: Mapped[str] = mapped_column(String(16))
    reason: Mapped[str] = mapped_column(String(32))
    value: Mapped[int] = mapped_column(BigInteger)
    # The user whose platform command caused it (T010); null for the button, the sensor, …
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
