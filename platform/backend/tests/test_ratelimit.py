import pytest
from starlette.requests import Request

from app.core import ratelimit
from app.core.config import get_settings
from app.core.errors import AppError

PASSWORD = "correct horse battery"


@pytest.fixture
def limits_on(monkeypatch):
    monkeypatch.setattr(get_settings(), "rate_limit_enabled", True)


def _request(peer: str, forwarded: str | None = None) -> Request:
    headers = [(b"x-forwarded-for", forwarded.encode())] if forwarded else []
    return Request({"type": "http", "client": (peer, 1234), "headers": headers})


def test_limit_allows_up_to_the_limit_then_refuses_with_retry_after(limits_on):
    limit = ratelimit.RateLimit("t", 2, 60)
    limit.hit("k")
    limit.hit("k")

    with pytest.raises(AppError) as error:
        limit.hit("k")

    assert (error.value.status, error.value.code) == (429, "rate_limited")
    assert 1 <= int(error.value.headers["Retry-After"]) <= 60


def test_limit_counts_each_key_separately(limits_on):
    limit = ratelimit.RateLimit("t", 1, 60)
    limit.hit("a")

    limit.hit("b")


def test_old_hits_leave_the_window(limits_on, monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(ratelimit.time, "monotonic", lambda: clock[0])
    limit = ratelimit.RateLimit("t", 1, 60)
    limit.hit("k")
    clock[0] += 61

    limit.hit("k")


def test_disabled_limits_never_refuse():
    limit = ratelimit.RateLimit("t", 1, 60)
    for _ in range(5):
        limit.hit("k")


async def test_login_start_is_limited_per_ip(client, limits_on, make_user):
    await make_user("ana@example.com")
    for _ in range(10):
        await client.post("/api/auth/login/start", json={"email": "ana@example.com"})

    response = await client.post("/api/auth/login/start", json={"email": "ana@example.com"})

    assert response.status_code == 429
    assert "retry-after" in response.headers


async def test_codes_sent_to_one_address_are_limited(client, limits_on, monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_self_signup", True)
    for _ in range(3):
        assert (
            await client.post("/api/auth/login/start", json={"email": "new@example.com"})
        ).status_code == 200

    response = await client.post("/api/auth/login/start", json={"email": "new@example.com"})

    assert response.json()["error"]["code"] == "rate_limited"


async def test_verify_is_limited_per_ip(client, limits_on, make_user):
    await make_user("ana@example.com")
    for _ in range(10):
        await client.post(
            "/api/auth/login/verify", json={"email": "x@example.com", "code": "123456"}
        )

    response = await client.post(
        "/api/auth/login/verify", json={"email": "ana@example.com", "password": PASSWORD}
    )

    assert response.status_code == 429


async def test_refresh_is_limited_per_ip(client, limits_on):
    for _ in range(30):
        await client.post("/api/auth/refresh")

    assert (await client.post("/api/auth/refresh")).status_code == 429


async def test_change_password_is_limited_per_user(client, limits_on, make_user):
    from app.core.security import create_access_token

    user = await make_user("ana@example.com")
    headers = {"Authorization": f"Bearer {create_access_token(user.id, 'user')}"}
    body = {"current_password": "wrong password!", "new_password": "a new long password"}
    for _ in range(5):
        await client.post("/api/auth/change-password", headers=headers, json=body)

    response = await client.post("/api/auth/change-password", headers=headers, json=body)

    assert response.status_code == 429


def test_client_ip_is_the_peer_without_trusted_proxies():
    assert ratelimit.client_ip(_request("203.0.113.7", "198.51.100.1")) == "203.0.113.7"


def test_client_ip_uses_forwarded_for_behind_a_trusted_proxy(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8, 192.168.1.1")

    ip = ratelimit.client_ip(_request("10.0.0.5", "198.51.100.1, 192.168.1.1"))

    assert ip == "198.51.100.1"


def test_client_ip_falls_back_to_the_peer_when_every_hop_is_trusted(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")

    assert ratelimit.client_ip(_request("10.0.0.5", "10.0.0.9")) == "10.0.0.5"


def test_client_ip_ignores_a_spoofed_header_from_an_untrusted_peer(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")

    assert ratelimit.client_ip(_request("203.0.113.7", "10.0.0.1")) == "203.0.113.7"


def test_client_ip_skips_garbage_entries(monkeypatch):
    monkeypatch.setattr(get_settings(), "trusted_proxies", "10.0.0.0/8")

    assert ratelimit.client_ip(_request("10.0.0.5", "not-an-ip, 10.0.0.2")) == "not-an-ip"


def test_client_ip_without_a_peer():
    request = Request({"type": "http", "client": None, "headers": []})

    assert ratelimit.client_ip(request) == "unknown"
