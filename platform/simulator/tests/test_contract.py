"""The simulator against the real board's contract.

Two sources, mounted read-only at $CONTRACT_DIR (devices/garage-iot-controller):
- README.md "API" section: the JSON examples, the event and reason names, the error table;
- firmware/http.cpp: the keys of every JSON answer, read from its format strings.
When the firmware's API changes, these tests fail until the simulator follows.
"""

import json
import os
import re
from pathlib import Path

import pytest
from conftest import Board

CONTRACT = Path(os.environ.get("CONTRACT_DIR", "/contract"))
README = (CONTRACT / "README.md").read_text()
HTTP_CPP = (CONTRACT / "firmware" / "http.cpp").read_text()
API = README[README.index("## API") : README.index("### Home Assistant mapping")]

# Codes the README's error table lists that a test cannot produce, and why.
NOT_PRODUCIBLE = {
    # Firmware updates are simulated in phase 3 (the simulator answers 501 not_simulated).
    "server_unreachable",
    "file_not_found",
}


def json_blocks(text: str) -> list[str]:
    return re.findall(r"```json\n(.*?)```", text, flags=re.S)


def shape(value):
    """Keys and value types, recursively; lists by their first element."""
    if isinstance(value, dict):
        return {k: shape(v) for k, v in value.items()}
    if isinstance(value, list):
        return [shape(value[0])] if value else []
    return type(value).__name__


def example(heading: str):
    section = API[API.index(heading) :]
    return json.loads(json_blocks(section)[0])


def cpp_keys(function: str) -> set[str]:
    """JSON keys written by a function of http.cpp (`\"key\":` in its format strings)."""
    start = HTTP_CPP.index(function)
    body = HTTP_CPP[start : HTTP_CPP.index("\n}\n", start)]
    return set(re.findall(r'\\"(\w+)\\":', body))


def all_keys(value) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for v in value.values() for k in all_keys(v)}
    if isinstance(value, list):
        return {k for v in value for k in all_keys(v)}
    return set()


def test_state_matches_the_readme_example(board: Board):
    assert shape(board.state()) == shape(example("### State"))


def test_log_matches_the_readme_example(board: Board):
    board.post("light/on")
    assert shape(board.get("log").json()) == shape(example("### Event log"))


def test_command_answer_matches_the_readme(board: Board):
    text = json_blocks(API[API.index("### Commands") :])[0]
    documented = json.loads(text.replace("{ ... }", "{}"))
    answer = board.post("light/on").json()
    assert set(answer) == set(documented)
    assert answer["result"] in ("ok", "noop")
    assert shape(answer["state"]) == shape(example("### State"))


def test_error_envelope_matches_the_readme(board: Board):
    documented = example("### Errors")
    assert shape(board.post("door/nope").json()) == shape(documented)


def test_answers_carry_the_keys_http_cpp_writes(board: Board):
    assert all_keys(board.get("info").json()) == cpp_keys("void respondInfo()")
    assert all_keys(board.state()) == cpp_keys("size_t stateJson(")
    # settingsJson adds "token" only in setup mode, which the simulator does not have.
    settings = board.get("settings", headers=board.auth).json()
    assert set(settings) == cpp_keys("size_t settingsJson(") - {"token"}


def test_info_entities_match_http_cpp(board: Board):
    ids = re.findall(r'\{\\"id\\":\\"(\w+)\\",\\"type\\":\\"(\w+)\\"', HTTP_CPP)
    assert [(e["id"], e["type"]) for e in board.get("info").json()["entities"]] == ids


def documented_list(label: str) -> set[str]:
    """Backticked names of a README bullet such as "- `event`: `boot`, `door_closed`, …"."""
    start = API.index(f"- `{label}`:")
    end = API.index("\n- ", start + 1)
    return set(re.findall(r"`([a-z_]+)`", API[start:end])) - {label}


def test_events_sources_and_reasons_are_documented(board: Board):
    g = board.device.garage
    board.post("light/on")
    board.post("door/open")
    board.post("settings", json={"name": "Other"})
    board.wait(21)
    for e in board.events():
        assert e["event"] in documented_list("event")
        assert e["source"] in documented_list("source")
    reasons_table = set(re.findall(r"^\| `([a-z_]+)` \|", API, flags=re.M))
    for e in g.log:
        assert e.reason == "none" or e.reason in reasons_table


def error_table() -> dict[str, int]:
    """Code → HTTP status, from the README's error table; `invalid_*` is kept as `invalid_`."""
    table = API[API.index("| Status | Code |") : API.index("`POST /settings` answers")]
    statuses = {}
    for status, row in re.findall(r"^\| (\d{3}) \| (.*?) \|", table, flags=re.M):
        for c in re.findall(r"`([a-z_]+\*?)`", row):
            statuses[c.rstrip("*")] = int(status)
    return statuses


def produce(board: Board) -> dict[str, int]:
    """Errors a client can get from the simulator, one request each: code → status."""
    out = {}

    def keep(r) -> None:
        out[r.json()["error"]["code"]] = r.status_code

    keep(board.post("light/on?duration=x"))
    keep(board.post("light/on", auth=False))
    keep(board.post("light/on", headers={"Origin": "http://evil.example"}))
    keep(board.post("door/nope"))
    keep(board.client.post("/api/v1/info"))
    board.post("door/open")
    keep(board.post("door/close"))
    for body in (
        {"name": ""},
        {"token": "x"},
        {"open_s": 1},
        {"close_s": 1},
        {"light_s": 1},
        {"night_level": 0},
        {"display": 1},
        {"wifi_ssid": ""},
        {"wifi_password": "short"},
    ):
        keep(board.post("settings", json=body))
    board.hook("fail_next_save")
    keep(board.post("settings", json={"name": "Lost"}))
    return out


def test_every_documented_error_is_produced_with_its_status(board: Board):
    table = error_table()
    assert table["door_busy"] == 409  # the table was found
    produced = produce(board)
    for c, status in table.items():
        if c in NOT_PRODUCIBLE:
            continue
        if c == "invalid_":  # the `invalid_*` row: every settings field and the duration
            wildcard = {p: s for p, s in produced.items() if p.startswith("invalid_")}
            assert len(wildcard) >= 9
            assert set(wildcard.values()) == {status}
        else:
            assert produced.get(c) == status, c


def test_http_cpp_answers_the_documented_statuses():
    """Every respondError(status, "code", …) in http.cpp matches the README table's status."""
    table = error_table()
    for status, c in re.findall(r'respondError\((\d{3}), "([a-z_]+)"', HTTP_CPP):
        expected = table.get(c, table["invalid_"] if c.startswith("invalid_") else None)
        if c in (
            "bad_request",
            "too_large",
            "setup_mode",
        ):  # transport and setup mode: not in the table
            continue
        assert expected == int(status), c


@pytest.mark.parametrize("code", sorted(NOT_PRODUCIBLE))
def test_exemptions_are_still_documented(code):
    assert code in error_table()
