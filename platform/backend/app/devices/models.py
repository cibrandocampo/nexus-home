"""Registered devices."""

from datetime import datetime

from sqlalchemy import DateTime, String, func
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
