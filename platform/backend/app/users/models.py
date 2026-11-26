"""User accounts."""

import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.core.db import Base


class Role(enum.StrEnum):
    none = "none"  # signed up, no permissions until an admin grants them
    user = "user"
    admin = "admin"


ROLE_LEVEL = {Role.none: 0, Role.user: 1, Role.admin: 2}


class AuthMethod(enum.StrEnum):
    otp = "otp"
    password = "password"  # noqa: S105 - login method name, not a credential


class Language(enum.StrEnum):
    en = "en"
    es = "es"
    gl = "gl"


class Theme(enum.StrEnum):
    system = "system"
    light = "light"
    dark = "dark"


def _enum(cls: type[enum.Enum]) -> Enum:
    # Stored as text with a check constraint: adding a value needs no Postgres enum migration.
    return Enum(
        cls,
        native_enum=False,
        create_constraint=True,
        length=16,
        values_callable=lambda e: [m.value for m in e],
    )


def normalise_email(value: str) -> str:
    return value.strip().lower()


class User(Base):
    __tablename__ = "users"
    # Stored lower-case even by writers that bypass the model, so equality lookups stay exact.
    __table_args__ = (CheckConstraint("email = lower(email)", name="email_lower"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254))
    first_name: Mapped[str] = mapped_column(String(100), default="")
    last_name: Mapped[str] = mapped_column(String(100), default="")
    auth_method: Mapped[AuthMethod] = mapped_column(_enum(AuthMethod), default=AuthMethod.otp)
    password_hash: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(_enum(Role), default=Role.none)
    is_active: Mapped[bool] = mapped_column(default=False)
    language: Mapped[Language] = mapped_column(_enum(Language), default=Language.en)
    theme: Mapped[Theme] = mapped_column(_enum(Theme), default=Theme.system)
    # IANA name, e.g. "Europe/Madrid". UTC until the user picks one (the app proposes the
    # browser's).
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set by the first successful login (code or password). Unset for sign-ups not yet confirmed.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    @validates("email")
    def _normalise_email(self, _key: str, value: str) -> str:
        return normalise_email(value)

    def has_role(self, minimum: Role) -> bool:
        return ROLE_LEVEL[self.role] >= ROLE_LEVEL[minimum]


# Unique regardless of case, also for writers that bypass the model.
Index("uq_users_email_lower", func.lower(User.email), unique=True)
