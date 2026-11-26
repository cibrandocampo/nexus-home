"""User representations shared by the auth and users APIs."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.types import Name, OptionalName, Secret, TimeZone
from app.users.models import AuthMethod, Language, Role, Theme


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    first_name: str
    last_name: str
    role: Role
    auth_method: AuthMethod
    language: Language
    theme: Theme
    timezone: str
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    first_name: Name | None = None
    last_name: Name | None = None
    language: Language | None = None
    theme: Theme | None = None
    timezone: TimeZone | None = None


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    first_name: OptionalName = ""
    last_name: OptionalName = ""
    role: Role = Role.user
    auth_method: AuthMethod = AuthMethod.otp
    password: Secret | None = None
    language: Language = Language.en


class UserUpdate(BaseModel):
    """Admin changes; every field is optional and null is not accepted."""

    model_config = ConfigDict(extra="forbid")

    first_name: OptionalName | None = None
    last_name: OptionalName | None = None
    role: Role | None = None
    is_active: bool | None = None
    auth_method: AuthMethod | None = None
    language: Language | None = None


class SetPassword(BaseModel):
    model_config = ConfigDict(extra="forbid")

    password: Secret


class UserPage(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    size: int
