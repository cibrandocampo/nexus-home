"""Application settings, read from the environment (see docs/configuration.md)."""

import base64
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    env: Literal["development", "test", "production"] = "production"
    app_name: str = "nexusHome"
    # Set by the image build (`APP_VERSION` build arg) and reported by /api/health.
    app_version: str = "dev"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Built frontend served by the API (the production image copies it here); absent in development.
    static_dir: str = "/app/static"
    database_url: str = "postgresql+asyncpg://app:app@db:5432/app"

    # Sessions
    # Signs access tokens. Production refuses this default (T010).
    secret_key: str = "change-me"  # noqa: S105 - placeholder, not a credential
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    # A refresh token presented again within this window after its rotation (parallel requests
    # from two tabs) is refused without revoking the session; later reuse revokes the family.
    refresh_reuse_grace_seconds: int = 10
    cookie_secure: bool = True  # false only for deployments served over plain HTTP
    bcrypt_rounds: int = 12

    # Public address of the app, used in emails
    site_url: str = "http://localhost:15173"

    # Email
    email_backend: Literal["smtp", "memory"] = "smtp"
    email_from: str = "nexusHome <no-reply@example.com>"
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: str | None = None
    smtp_tls: Literal["none", "starttls", "ssl"] = "starttls"
    smtp_timeout_seconds: float = 10

    # Login
    allow_self_signup: bool = False  # anyone can create an account (it starts without permissions)
    otp_minutes: int = 10
    otp_max_attempts: int = 5
    lockout_attempts: int = 5  # failed passwords within lockout_minutes lock password login
    lockout_minutes: int = 15
    unverified_signup_days: int = 7  # sign-ups never confirmed with a code are deleted after this
    block_disposable_email: bool = True
    disposable_email_extra_domains: str = ""  # comma-separated
    disposable_email_allow_domains: str = ""  # comma-separated

    # Rate limits (in memory, per process) and the proxies whose X-Forwarded-For is trusted
    rate_limit_enabled: bool = True
    trusted_proxies: str = ""  # comma-separated IPs or CIDRs

    # First administrator, created at start-up when no admin exists
    admin_email: str | None = None
    admin_password: str | None = None

    # Devices
    # Fernet key for the device tokens at rest (url-safe base64 of 32 bytes). Production refuses
    # this development default; losing the key means re-entering every device token.
    device_token_key: str = "w8okSphRDml6-rycgRvw2UAF5b4bdrWFKXFg4HpCNl8="  # noqa: S105 - dev key
    device_timeout_s: float = 3.0  # per request to a board


DEFAULT_SECRET_KEY = Settings.model_fields["secret_key"].default
DEFAULT_DEVICE_TOKEN_KEY = Settings.model_fields["device_token_key"].default
MIN_SECRET_BYTES = 32


def production_problems(settings: Settings) -> list[str]:
    """What makes these settings unsafe to run in production (empty outside production)."""
    if settings.env != "production":
        return []
    problems = []
    if settings.secret_key == DEFAULT_SECRET_KEY:
        problems.append("SECRET_KEY is the default placeholder")
    elif len(settings.secret_key.encode()) < MIN_SECRET_BYTES:
        problems.append(f"SECRET_KEY is shorter than {MIN_SECRET_BYTES} bytes")
    if settings.device_token_key == DEFAULT_DEVICE_TOKEN_KEY:
        problems.append("DEVICE_TOKEN_KEY is the development key")
    elif not _valid_fernet_key(settings.device_token_key):
        problems.append("DEVICE_TOKEN_KEY is not a Fernet key (url-safe base64 of 32 bytes)")
    return problems


def _valid_fernet_key(key: str) -> bool:
    try:
        return len(base64.urlsafe_b64decode(key.encode())) == 32 and len(key) == 44
    except ValueError:
        return False


def ensure_production_ready(settings: Settings) -> None:
    problems = production_problems(settings)
    if problems:
        raise RuntimeError(
            "Refusing to start in production: "
            + "; ".join(problems)
            + ". Set a long random SECRET_KEY (for example: openssl rand -hex 32) and a new"
            + " DEVICE_TOKEN_KEY (openssl rand -base64 32 | tr '+/' '-_');"
            + " see docs/configuration.md."
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
