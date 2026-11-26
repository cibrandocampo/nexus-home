"""In-memory sliding-window rate limits (one app process) and the client's IP address."""

import ipaddress
import math
import time
from collections import defaultdict, deque
from functools import lru_cache

from fastapi import Request

from app.core.config import get_settings
from app.core.errors import AppError


class RateLimit:
    def __init__(self, name: str, limit: int, seconds: int) -> None:
        self.name = name
        self.limit = limit
        self.seconds = seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def hit(self, key: str) -> None:
        """Count one request for `key`; raise 429 rate_limited when over the limit."""
        if not get_settings().rate_limit_enabled:
            return
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] <= now - self.seconds:
            hits.popleft()
        if len(hits) >= self.limit:
            retry = max(1, math.ceil(hits[0] + self.seconds - now))
            raise AppError(
                429,
                "rate_limited",
                "Too many requests, try again later",
                headers={"Retry-After": str(retry)},
            )
        hits.append(now)

    def prune(self) -> None:
        """Forget keys whose hits all left the window (keeps memory bounded)."""
        cutoff = time.monotonic() - self.seconds
        for key in [k for k, hits in self._hits.items() if not hits or hits[-1] <= cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        self._hits.clear()


LOGIN_START_IP = RateLimit("login_start_ip", 10, 3600)
LOGIN_EMAIL = RateLimit("login_email", 3, 3600)  # emails sent to one address
LOGIN_VERIFY_IP = RateLimit("login_verify_ip", 10, 60)
REFRESH_IP = RateLimit("refresh_ip", 30, 60)
CHANGE_PASSWORD_USER = RateLimit("change_password_user", 5, 3600)
ALL = (LOGIN_START_IP, LOGIN_EMAIL, LOGIN_VERIFY_IP, REFRESH_IP, CHANGE_PASSWORD_USER)


@lru_cache
def _trusted_networks() -> tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]:
    raw = get_settings().trusted_proxies
    return tuple(ipaddress.ip_network(p.strip(), strict=False) for p in raw.split(",") if p.strip())


def _trusted(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in network for network in _trusted_networks())


def client_ip(request: Request) -> str:
    """Peer address, or the nearest untrusted X-Forwarded-For address behind a trusted proxy."""
    peer = request.client.host if request.client else "unknown"
    if not _trusted(peer):
        return peer
    forwarded = [a.strip() for a in request.headers.get("x-forwarded-for", "").split(",")]
    for address in reversed([a for a in forwarded if a]):
        if not _trusted(address):
            return address
    return peer
