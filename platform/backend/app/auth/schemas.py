"""Request and response bodies of /api/auth."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr

from app.core.types import Code, Secret
from app.users.schemas import UserOut


class AuthConfig(BaseModel):
    allow_self_signup: bool


class LoginStart(BaseModel):
    email: EmailStr


class LoginStartResult(BaseModel):
    method: Literal["otp", "password"]


class LoginVerify(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    # Exactly one of code and password (checked by the endpoint).
    code: Code | None = None
    password: Secret | None = None


class SessionOut(BaseModel):
    access_token: str
    user: UserOut


class LoginResult(SessionOut):
    is_new: bool


class ChangePassword(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: Secret | None = None
    new_password: Secret
