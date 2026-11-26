"""HTTP rules (http.cpp handle), settings, restart and the test hooks."""

import asyncio

import pytest
from conftest import TOKEN, Board
from starlette.testclient import TestClient

from sim import app as app_module
from sim.app import create_app, device_from_env, make_app, parse_body
from sim.device import Identity


def code(r) -> tuple[int, str]:
    return r.status_code, r.json()["error"]["code"]


def test_info_describes_the_board_and_its_entities(board: Board):
    info = board.get("info").json()
    assert info["id"] == info["hostname"] == "garage-abc123"
    assert (info["mode"], info["api"], info["auth"], info["reset_reason"]) == (
        "normal",
        "v1",
        True,
        "power",
    )
    assert info["mac"].count(":") == 5
    assert [e["id"] for e in info["entities"]] == [
        "door",
        "light",
        "door_problem",
        "night",
        "light_level",
        "rssi",
    ]


def test_state_reports_the_wifi(board: Board):
    wifi = board.state()["wifi"]
    assert wifi["ip"] == "10.0.0.9"
    assert -61 <= wifi["rssi"] <= -55


def test_methods_and_paths(board: Board):
    assert code(board.client.post("/api/v1/info")) == (405, "method_not_allowed")
    assert code(board.client.post("/api/v1/state", headers=board.auth)) == (
        405,
        "method_not_allowed",
    )
    assert code(board.client.get("/api/v1/door/open")) == (405, "method_not_allowed")
    assert code(board.client.put("/api/v1/light/on")) == (405, "method_not_allowed")
    assert code(board.post("door/nope")) == (404, "not_found")
    assert code(board.client.get("/elsewhere")) == (404, "not_found")
    assert board.client.get("/").headers["content-type"].startswith("text/html")
    assert code(board.client.post("/")) == (405, "method_not_allowed")


def test_posts_and_settings_need_the_token(board: Board):
    assert code(board.post("light/on", auth=False)) == (401, "unauthorized")
    assert code(board.post("light/on", headers={"Authorization": "Bearer wrong-token"})) == (
        401,
        "unauthorized",
    )
    assert code(board.post("light/on", headers={"Authorization": TOKEN})) == (401, "unauthorized")
    assert code(board.get("settings")) == (401, "unauthorized")
    assert board.get("settings", headers=board.auth).status_code == 200
    ok = board.post("light/on", auth=False, headers={"Authorization": f"bearer {TOKEN}"})
    assert ok.status_code == 200
    assert board.get("state").status_code == 200  # GETs are open


def test_a_board_without_a_token_is_open():
    b = Board(token="")
    assert b.post("light/on").status_code == 200
    assert b.get("settings").status_code == 200
    assert b.get("info").json()["auth"] is False


def test_cross_origin_posts_are_rejected(board: Board):
    r = board.post("light/off", headers={"Origin": "http://evil.example"})
    assert code(r) == (403, "forbidden")
    same = board.post("light/off", headers={"Origin": "http://testserver"})
    assert same.status_code == 200


def test_settings_are_read_without_secrets(board: Board):
    s = board.get("settings", headers=board.auth).json()
    assert s == {
        "name": "Garage",
        "wifi_ssid": "nexus-sim",
        "wifi_password_set": True,
        "token_set": True,
        "open_s": 20,
        "close_s": 40,
        "light_s": 120,
        "night_level": 700,
        "display": True,
        "stored": True,
        "wifi_trying": False,
    }


def test_settings_change_applies_and_is_logged(board: Board):
    r = board.post("settings", json={"name": "Garaxe", "open_s": 10, "display": False})
    assert r.json()["result"] == "ok"
    assert r.json()["settings"]["name"] == "Garaxe"
    assert board.events()[0] == {
        "t": 0,
        "event": "settings_changed",
        "source": "api",
        "reason": "none",
        "value": 0,
    }
    assert board.get("info").json()["name"] == "Garaxe"
    assert board.state()["display"] is False
    board.post("door/open")
    board.wait(10.2)
    assert board.door() == "open"  # the new opening time
    before = len(board.events())
    assert board.post("settings", json={"name": "Garaxe"}).json()["result"] == "ok"
    assert len(board.events()) == before  # nothing changed: nothing saved


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ({"name": ""}, "invalid_name"),
        ({"name": "x" * 33}, "invalid_name"),
        ({"name": 3}, "invalid_name"),
        ({"token": "short"}, "invalid_token"),
        ({"token": "has a space"}, "invalid_token"),
        ({"token": ""}, "invalid_token"),
        ({"token": "t" * 65}, "invalid_token"),
        ({"open_s": 4}, "invalid_open_time"),
        ({"open_s": 101}, "invalid_open_time"),
        ({"open_s": "20"}, "invalid_open_time"),
        ({"open_s": 2.5}, "invalid_open_time"),
        ({"close_s": 9}, "invalid_close_time"),
        ({"light_s": 601}, "invalid_light_time"),
        ({"night_level": 0}, "invalid_night_level"),
        ({"night_level": 70000}, "invalid_night_level"),
        ({"display": "yes"}, "invalid_display"),
        ({"wifi_ssid": ""}, "invalid_ssid"),
        ({"wifi_ssid": "n" * 33}, "invalid_ssid"),
        ({"wifi_password": "short"}, "invalid_password"),
        ({"wifi_password": "p" * 64}, "invalid_password"),
    ],
)
def test_invalid_settings_are_refused(board: Board, body, expected):
    r = board.post("settings", json=body)
    assert code(r) == (400, expected)
    assert r.json()["error"]["message"]


def test_settings_body_must_be_a_json_object(board: Board):
    r = board.post("settings", content=b"{not json", headers={"Content-Type": "application/json"})
    assert code(r) == (400, "invalid_json")


def test_a_new_token_replaces_the_old_one(board: Board):
    board.post("settings", json={"token": "new-token-5678"})
    assert board.post("light/on").status_code == 401
    ok = board.post("light/on", auth=False, headers={"Authorization": "Bearer new-token-5678"})
    assert ok.status_code == 200


def test_a_new_wifi_network_answers_testing_wifi(board: Board):
    r = board.post("settings", json={"wifi_ssid": "other", "wifi_password": "other-pass"})
    assert r.json()["result"] == "testing_wifi"
    assert r.json()["settings"]["wifi_ssid"] == "other"
    assert board.events()[0]["event"] == "wifi_changed"
    same = board.post("settings", json={"wifi_ssid": "other", "wifi_password": ""})
    assert same.json()["result"] == "ok"  # an empty password keeps the current one


def test_a_failed_save_is_reported_and_logged(board: Board):
    board.hook("fail_next_save")
    r = board.post("settings", json={"name": "Lost"})
    assert code(r) == (500, "save_failed")
    assert board.events()[0]["event"] == "settings_save_failed"
    assert board.get("info").json()["name"] == "Garage"


def test_restart_is_refused_while_the_door_moves(board: Board):
    board.post("door/open")
    assert code(board.post("restart")) == (409, "door_busy")


def test_restart_reboots_after_the_answer(board: Board):
    board.post("light/on")
    assert board.post("restart").json() == {"result": "restarting"}
    assert board.device.down_for() == pytest.approx(2.0)
    board.wait(2.5)
    assert board.device.down_for() == 0
    info = board.get("info").json()
    assert info["reset_reason"] == "software"
    s = board.state()
    assert (s["uptime_s"], s["light"]["state"]) == (2, "off")
    assert [e["event"] for e in board.events()][-1] == "boot"


def test_firmware_updates_are_not_simulated_yet(board: Board):
    assert code(board.post("firmware", json={"url": "http://x/y.ota"})) == (501, "not_simulated")


def test_offline_hook_silences_the_board(board: Board):
    board.hook("offline", {"seconds": 30})
    assert board.device.down_for() == pytest.approx(30)
    board.wait(31)
    assert board.device.down_for() == 0


def test_a_silent_board_answers_only_after_it_is_back(board: Board, monkeypatch):
    waited = []

    async def fake_sleep(seconds):
        waited.append(seconds)
        board.clock.t += seconds

    monkeypatch.setattr(app_module.asyncio, "sleep", fake_sleep)
    board.hook("offline", {"seconds": 5})
    assert board.get("info").status_code == 200
    assert waited == [pytest.approx(5)]


def test_power_cycle_and_status_hooks(board: Board):
    board.post("restart")
    board.wait(3)
    board.hook("power_cycle")
    assert board.get("info").json()["reset_reason"] == "power"
    status = board.client.get("/sim/status").json()
    assert status == {
        "position": 0.0,
        "motion": 0,
        "obstructed": False,
        "uptime_s": 0,
        "speed": 1.0,
    }
    assert code(board.client.get("/sim/button")) == (405, "method_not_allowed")
    assert code(board.hook("nope")) == (404, "not_found")


def test_hooks_can_be_switched_off():
    b = Board(hooks=False)
    assert code(b.client.post("/sim/button")) == (404, "not_found")


def test_parse_body():
    assert parse_body(b"") == {}
    assert parse_body(b"[1]") is None
    assert parse_body(b'{"a": 1}') == {"a": 1}


def test_configuration_from_the_environment():
    d = device_from_env(
        {
            "SIM_ID": "garage-0000aa",
            "SIM_TOKEN": "env-token-123",
            "SIM_NAME": "Bench",
            "SIM_VERSION": "2.1.0",
            "SIM_SPEED": "10",
            "SIM_LIGHT_LEVEL": "800",
            "SIM_IP": "10.9.9.9",
        }
    )
    assert (d.identity.id, d.identity.version, d.identity.ip) == (
        "garage-0000aa",
        "2.1.0",
        "10.9.9.9",
    )
    assert (d.settings.name, d.settings.token, d.speed) == ("Bench", "env-token-123", 10.0)
    assert d.garage.base_light_level == 800
    assert device_from_env({}).identity.ip  # resolved from the container's hostname


def test_default_ip_falls_back_to_loopback(monkeypatch):
    def boom(*_):
        raise OSError

    monkeypatch.setattr(app_module.socket, "gethostbyname", boom)
    assert app_module.default_ip() == "127.0.0.1"


def test_speed_runs_simulated_time_faster():
    b = Board()
    b.device.speed = 10
    b.post("door/open")
    b.wait(2.1)
    assert b.door() == "open"


def test_fractions_of_a_tick_add_up(board: Board):
    for _ in range(8):
        board.wait(0.0078125)  # 0.78125 ticks each, exact in binary: 6.25 ticks in all
    assert board.device.garage.ticks == 6


def test_the_app_factory_and_its_background_clock(monkeypatch):
    monkeypatch.setenv("SIM_HOOKS", "0")
    monkeypatch.setattr(app_module, "SYNC_EVERY_S", 0.01)
    app = create_app()
    with TestClient(app) as client:
        assert client.get("/api/v1/info").status_code == 200
        assert client.post("/sim/button").status_code == 404
        before = app.state.device.garage.ticks
        client.portal.call(asyncio.sleep, 0.2)
        assert app.state.device.garage.ticks > before


def test_identity_mac_is_stable_and_local():
    a, b = Identity(id="garage-111111"), Identity(id="garage-111111")
    assert a.mac == b.mac
    assert a.mac.startswith("02:")


def test_make_app_without_hooks_or_background():
    b = Board()
    app = make_app(b.device, hooks=False, background=False)
    with TestClient(app) as client:
        assert client.get("/api/v1/state").status_code == 200
