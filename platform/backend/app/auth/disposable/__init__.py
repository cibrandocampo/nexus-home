"""Disposable email domains blocked at sign-up."""

from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings

HERE = Path(__file__).parent
FILES = ("disposable_email_domains.txt", "disposable_email_domains.local.txt")


def _read(path: Path) -> set[str]:
    lines = (line.strip().lower() for line in path.read_text().splitlines())
    return {line for line in lines if line and not line.startswith("#")}


def _split(value: str) -> set[str]:
    return {d.strip().lower() for d in value.split(",") if d.strip()}


@lru_cache
def blocked_domains() -> frozenset[str]:
    settings = get_settings()
    domains = set().union(*(_read(HERE / name) for name in FILES))
    domains |= _split(settings.disposable_email_extra_domains)
    domains -= _split(settings.disposable_email_allow_domains)
    return frozenset(domains)


def is_disposable(email: str) -> bool:
    """True when the email's domain, or any parent domain, is blocked."""
    if not get_settings().block_disposable_email:
        return False
    labels = email.rpartition("@")[2].lower().split(".")
    blocked = blocked_domains()
    return any(".".join(labels[i:]) in blocked for i in range(len(labels) - 1))
