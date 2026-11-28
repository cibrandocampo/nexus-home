import asyncio
import json

import httpx
import pytest
from cryptography.fernet import Fernet

from app.core.config import get_settings
from app.core.errors import AppError
from app.devices.client import DeviceClient, DeviceError
from app.devices.crypto import decrypt_token, encrypt_token
from app.devices.service import device_error
from tests.fakeboard import FakeBoard

HOST = "10.1.3.50"


async def test_bodies_are_raw_utf8_never_escaped(lan):
    board = lan.add(HOST)

    await DeviceClient(HOST, "board-token-1").post("settings", {"name": "Garaxe ñ"})

    request = board.requests[-1]
    assert request.content == json.dumps({"name": "Garaxe ñ"}, ensure_ascii=False).encode()
    assert b"\\u" not in request.content
    assert request.headers["Content-Type"] == "application/json"
    assert board.name == "Garaxe ñ"


async def test_every_request_closes_the_connection_and_auth_is_sent_only_when_asked(lan):
    board = lan.add(HOST)
    device = DeviceClient(HOST, "board-token-1")

    await device.info()
    await device.log()
    await device.settings()

    info, log, settings = board.requests
    assert log.url.path == "/api/v1/log"
    assert info.headers["Connection"] == "close"
    assert "Authorization" not in info.headers
    assert settings.headers["Authorization"] == "Bearer board-token-1"


async def test_no_authorization_header_without_a_token(lan):
    board = lan.add(HOST, FakeBoard(token=None))

    await DeviceClient(HOST).post("settings", {"name": "Bench"})

    assert "Authorization" not in board.requests[-1].headers


async def test_requests_to_one_board_never_overlap(lan):
    board = lan.add(HOST)
    board.delay_s = 0.02
    device = DeviceClient(HOST, "board-token-1")

    await asyncio.gather(*(device.state() for _ in range(5)))

    assert board.max_in_flight == 1


async def test_different_boards_are_not_serialised(lan):
    a = lan.add("10.1.3.50")
    b = lan.add("10.1.3.51")
    a.delay_s = b.delay_s = 0.05

    await asyncio.gather(DeviceClient("10.1.3.50").state(), DeviceClient("10.1.3.51").state())

    assert (len(a.requests), len(b.requests)) == (1, 1)
    assert (
        lan.max_in_flight == 2
    )  # the two requests overlapped: one lock per host, not a global one


async def test_timeouts_and_refused_connections_are_unreachable(lan):
    lan.add(HOST).unreachable = True

    with pytest.raises(DeviceError) as caught:
        await DeviceClient(HOST).state()

    assert (caught.value.status, caught.value.code) == (None, "device_unreachable")


async def test_the_timeout_comes_from_the_settings(monkeypatch):
    monkeypatch.setenv("DEVICE_TIMEOUT_S", "0.5")
    get_settings.cache_clear()
    try:
        assert DeviceClient(HOST).timeout == 0.5
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize(
    ("answer", "status", "code"),
    [
        (httpx.Response(200, text="<html>"), 200, "device_bad_answer"),
        (httpx.Response(200, json=[1, 2]), 200, "device_bad_answer"),
        (
            httpx.Response(409, json={"error": {"code": "door_busy", "message": "m"}}),
            409,
            "door_busy",
        ),
        (httpx.Response(500, text="oops"), 500, "device_error"),
        (httpx.Response(500, json={"error": "flat"}), 500, "device_error"),
    ],
)
async def test_answers_that_are_not_what_was_expected(lan, answer, status, code):
    lan.add(HOST).raw["state"] = answer

    with pytest.raises(DeviceError) as caught:
        await DeviceClient(HOST).state()

    assert (caught.value.status, caught.value.code) == (status, code)


async def test_redirects_are_not_followed(lan):
    board = lan.add(HOST)
    board.raw["state"] = httpx.Response(302, headers={"Location": "http://10.1.3.51/api/v1/state"})

    with pytest.raises(DeviceError) as caught:
        await DeviceClient(HOST).state()

    assert caught.value.status == 302
    assert len(board.requests) == 1


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (DeviceError(None, "device_unreachable"), 502, "device_unreachable"),
        (DeviceError(401, "unauthorized"), 409, "device_token_invalid"),
        (DeviceError(500, "save_failed"), 502, "device_error"),
    ],
)
def test_board_failures_as_the_platform_reports_them(error, status, code):
    mapped = device_error(error)

    assert (mapped.status, mapped.code) == (status, code)


# ---- tokens at rest ----


def test_tokens_round_trip_and_are_not_stored_in_clear():
    encrypted = encrypt_token("board-token-1")

    assert "board-token-1" not in encrypted
    assert decrypt_token(encrypted) == "board-token-1"
    assert encrypt_token("board-token-1") != encrypted  # random IV each time


def test_a_token_encrypted_with_another_key_is_unreadable():
    other = Fernet(Fernet.generate_key()).encrypt(b"board-token-1").decode()

    with pytest.raises(AppError) as caught:
        decrypt_token(other)

    assert (caught.value.status, caught.value.code) == (409, "device_token_unreadable")


async def test_a_board_that_stops_answering_mid_request_is_unreachable(lan):
    board = lan.add(HOST)

    def hang(request):
        raise httpx.ReadTimeout("read timed out", request=request)

    board.answer = hang  # connected, then no answer within the timeout

    with pytest.raises(DeviceError) as caught:
        await DeviceClient(HOST).state()

    assert (caught.value.status, caught.value.code) == (None, "device_unreachable")


async def test_proxies_from_the_environment_are_ignored(lan, monkeypatch):
    lan.add(HOST)
    seen = {}
    real = httpx.AsyncClient

    def spy(**kwargs):
        seen.update(kwargs)
        return real(**kwargs)

    monkeypatch.setenv("HTTP_PROXY", "http://proxy.invalid:3128")
    monkeypatch.setattr(httpx, "AsyncClient", spy)

    await DeviceClient(HOST).state()

    assert seen["trust_env"] is False
    assert seen["follow_redirects"] is False


@pytest.mark.parametrize("bad", ["\\u0000", "\\ud800"])
async def test_answers_the_database_could_not_hold_are_bad_answers(lan, bad):
    body = '{"rev": 1, "wifi": {"ip": "10.1.3.50' + bad + '"}}'
    lan.add(HOST).raw["state"] = httpx.Response(200, content=body.encode())

    with pytest.raises(DeviceError) as caught:
        await DeviceClient(HOST).state()

    assert caught.value.code == "device_bad_answer"


def test_storable_walks_keys_lists_and_values():
    from app.devices.client import storable

    assert storable({"a": [1, "ñ", {"b": None}], "c": True})
    assert not storable({"a\x00": 1})
    assert not storable({"a": ["\ud800"]})
