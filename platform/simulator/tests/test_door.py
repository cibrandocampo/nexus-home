"""Door and light behaviour, as the garage README "Behaviour" section and garage.cpp describe it."""

from conftest import Board


def test_boot_reads_the_door_from_the_sensor_and_logs_it(board: Board):
    s = board.state()
    assert s["door"] == {
        "state": "closed",
        "moving": False,
        "sensor_closed": True,
        "close_failed": False,
        "stopped": "none",
        "since_s": 0,
        "last_source": "none",
    }
    assert [e["event"] for e in board.events()] == ["wifi_up", "door_closed", "boot"]
    assert board.events()[1]["reason"] == "startup"


def test_open_runs_for_the_travel_time_then_reports_open(board: Board):
    r = board.post("door/open")
    assert r.status_code == 200
    assert r.json()["result"] == "ok"
    assert r.json()["state"]["door"]["state"] == "opening"
    board.wait(10)
    assert board.state()["door"]["moving"] is True
    board.wait(10.5)
    s = board.state()
    assert s["door"]["state"] == "open"
    assert s["door"]["last_source"] == "api"
    assert board.events()[0] == {
        "t": 20,
        "event": "door_open",
        "source": "api",
        "reason": "travel_end",
        "value": 0,
    }


def test_open_again_is_a_noop_and_close_confirms_with_the_sensor(board: Board):
    board.post("door/open")
    board.wait(21)
    assert board.post("door/open").json()["result"] == "noop"
    assert board.post("door/close").json()["state"]["door"]["state"] == "closing"
    board.wait(20)
    assert board.door() == "closed"
    assert board.events()[0]["reason"] == "sensor_closed"
    assert board.post("door/close").json()["result"] == "noop"


def test_opposite_command_while_moving_is_door_busy(board: Board):
    board.post("door/open")
    r = board.post("door/close")
    assert r.status_code == 409
    assert r.json() == {
        "error": {
            "code": "door_busy",
            "message": "Door is moving or was just triggered, retry later",
        }
    }


def test_a_second_pulse_within_the_gap_is_busy(board: Board):
    board.post("door/toggle")
    assert board.post("door/toggle").status_code == 409
    board.wait(1.3)
    assert board.post("door/toggle").status_code == 200


def test_stop_part_way_then_open_reverses_with_three_pulses(board: Board):
    board.post("door/open")
    board.wait(8)
    r = board.post("door/stop").json()["state"]["door"]
    assert (r["state"], r["stopped"]) == ("open", "up")
    board.wait(1.3)
    assert board.post("door/open").json()["result"] == "ok"
    assert board.post("door/open").status_code == 409  # pulses still to send
    board.wait(1.3)
    assert board.state()["door"]["state"] == "open"  # second pulse stopped the wrong-way move
    board.wait(1.3)
    assert board.door() == "opening"
    board.wait(25)
    assert board.door() == "open"
    assert board.device.garage.opener.position == 1.0


def test_stop_cancels_pending_pulses_and_is_noop_when_still(board: Board):
    assert board.post("door/stop").json()["result"] == "noop"
    board.post("door/open")
    board.wait(8)
    board.post("door/stop")
    board.wait(1.3)
    board.post("door/close")  # stopped going up: the next pulse closes, one pulse
    board.wait(1.3)
    board.post("door/stop")
    board.wait(1.3)
    assert board.state()["door"]["stopped"] == "down"
    board.post("door/close")  # stopped going down: three pulses queued
    # garage.cpp doorStop: the pending pulses are cancelled, but the door is moving and the last
    # pulse was under 1.2 s ago, so the stop pulse itself is refused: 409 although it cancelled.
    assert board.post("door/stop").status_code == 409
    assert board.device.garage.queued == 0


def test_close_while_stopped_going_down_reverses_and_closes(board: Board):
    board.post("door/open")
    board.wait(21)
    board.post("door/close")
    board.wait(5)
    board.post("door/stop")
    board.wait(1.3)
    assert board.post("door/close").json()["result"] == "ok"
    assert board.post("door/close").status_code == 409
    board.wait(30)
    assert board.door() == "closed"


def test_an_obstructed_close_is_reported_as_failed(board: Board):
    board.post("door/open")
    board.wait(21)
    board.hook("obstruct", {"on": True})
    board.post("door/close")
    board.wait(41)
    s = board.state()["door"]
    assert (s["state"], s["close_failed"]) == ("open", True)
    e = board.events()[0]
    assert (e["event"], e["value"]) == ("close_failed", 40)
    board.hook("obstruct", {"on": False})
    board.wait(1.3)
    board.post("door/close")
    assert board.state()["door"]["close_failed"] is False  # a new pulse is judged again


def test_a_door_moved_by_hand_is_seen_by_the_sensor(board: Board):
    board.hook("door", {"position": 1})
    board.wait(1)
    s = board.state()["door"]
    assert (s["state"], s["last_source"]) == ("opening", "sensor")
    assert board.events()[0]["reason"] == "sensor_released"
    board.wait(20)
    assert board.door() == "open"
    board.hook("door", {"position": 0})
    board.wait(1)
    assert board.door() == "closed"


def test_the_sensor_coming_back_during_an_opening_means_closed(board: Board):
    board.post("door/open")
    board.wait(5)  # past the settle time, the door has left the sensor
    board.hook("door", {"position": 0})
    board.wait(0.2)
    assert board.door() == "closed"
    assert board.events()[0]["reason"] == "came_back"


def test_an_opening_that_never_leaves_the_sensor_stays_closed(board: Board):
    board.device.garage.opener.up_s = 10_000  # the motor does not move the door
    board.device.garage.opener.position = 0.0
    board.post("door/open")
    board.device.garage.opener.motion = 0
    board.wait(21)
    assert board.door() == "closed"
    assert board.events()[0]["reason"] == "no_movement"


def test_the_button_pulses_like_the_api_and_too_soon_is_ignored(board: Board):
    board.hook("button")
    board.wait(0.1)
    s = board.state()["door"]
    assert (s["state"], s["last_source"]) == ("opening", "button")
    board.wait(0.3)
    board.hook("button")
    board.wait(0.3)
    assert board.events()[0]["event"] == "button_ignored"
    assert board.events()[0]["reason"] == "too_soon"


def test_night_comes_after_a_minute_and_opening_turns_the_light_on(board: Board):
    board.hook("light_level", {"level": 900})
    board.wait(65)  # the lamp settle time after boot (10 s) holds the decision back first
    assert board.state()["night"] is False
    board.wait(7)
    assert board.state()["night"] is True
    assert board.events()[0]["event"] == "night"
    board.post("door/open")
    light = board.state()["light"]
    assert (light["state"], light["timed"], light["remaining_s"]) == ("on", True, 120)
    assert any(e["event"] == "light_on" and e["source"] == "auto" for e in board.events())
    board.wait(121)
    assert board.state()["light"]["state"] == "off"
    board.hook("light_level", {"level": 100})
    board.wait(75)  # the lamp settle time, then a minute of day
    assert board.state()["night"] is False


def test_light_level_moves_without_changing_rev(board: Board):
    board.hook("light_level", {"level": 500})
    rev = board.state()["rev"]
    board.wait(3)
    s = board.state()
    assert s["rev"] == rev
    assert 497 <= s["light_level"] <= 503


def test_light_on_with_and_without_a_timer(board: Board):
    r = board.post("light/on?duration=600").json()["state"]["light"]
    assert (r["state"], r["timed"], r["remaining_s"]) == ("on", True, 600)
    r = board.post("light/on", json={"duration": 0}).json()["state"]["light"]
    assert (r["timed"], r["remaining_s"]) == (False, 0)
    assert board.post("light/on?duration=0").json()["result"] == "noop"
    assert board.post("light/on").json()["state"]["light"]["remaining_s"] == 120
    assert board.post("light/off").json()["result"] == "ok"
    assert board.post("light/off").json()["result"] == "noop"
    assert board.post("light/toggle").json()["state"]["light"]["state"] == "on"
    assert board.post("light/toggle").json()["state"]["light"]["state"] == "off"
    on = [e for e in board.events() if e["event"] == "light_on"]
    assert [e["value"] for e in on][-2:] == [0, 600]


def test_invalid_durations_are_refused(board: Board):
    for bad in ("light/on?duration=abc", "light/on?duration=90000", "light/on?duration="):
        r = board.post(bad)
        assert (r.status_code, r.json()["error"]["code"]) == (400, "invalid_duration")
    for body in ({"duration": -1}, {"duration": "30"}, {"duration": True}, {"duration": 90000}):
        assert board.post("light/on", json=body).json()["error"]["code"] == "invalid_duration"


def test_a_body_duration_is_read_up_to_its_first_non_digit(board: Board):
    # http.cpp findDuration: strtoul after `"duration"` and its colon, so 30.5 is 30 s.
    light = board.post("light/on", json={"duration": 30.5}).json()["state"]["light"]
    assert light["remaining_s"] == 30
    light = board.post("light/on?x=1&duration=45").json()["state"]["light"]
    assert light["remaining_s"] == 45


def test_open_while_closing_is_busy_and_open_after_a_stopped_close_is_one_pulse(board: Board):
    board.post("door/open")
    board.wait(21)
    board.post("door/close")
    board.wait(1.3)
    assert board.post("door/open").status_code == 409  # opposite movement in progress
    board.post("door/stop")
    board.wait(1.3)
    assert board.state()["door"]["stopped"] == "down"
    assert board.post("door/open").json()["state"]["door"]["state"] == "opening"  # one pulse
    assert board.device.garage.queued == 0


def test_a_reversal_is_refused_inside_the_pulse_gap(board: Board):
    board.post("door/open")
    board.wait(8)
    board.post("door/stop")  # stopped going up: open needs a reversal, but the gap is running
    assert board.post("door/open").status_code == 409


def test_auto_light_leaves_a_light_held_on_by_hand(board: Board):
    board.hook("light_level", {"level": 900})
    board.wait(72)
    board.post("light/on?duration=0")
    board.post("door/open")
    light = board.state()["light"]
    assert (light["state"], light["timed"]) == ("on", False)


def test_a_new_night_level_applies_at_once(board: Board):
    # garage.cpp configure runs decideNight(true): raising the level above the reading ends night.
    board.hook("light_level", {"level": 690})
    board.post("settings", json={"night_level": 680})
    board.wait(72)
    assert board.state()["night"] is True
    board.post("settings", json={"night_level": 695})
    board.wait(61)
    assert board.state()["night"] is False
    assert board.events()[0]["event"] == "day"


def test_every_change_increases_rev(board: Board):
    rev = board.state()["rev"]
    board.post("light/on")
    assert board.state()["rev"] > rev


def test_the_log_keeps_the_last_64_events(board: Board):
    for _ in range(70):
        board.post("light/toggle")
    log = board.get("log").json()
    assert len(log["events"]) == 64
    assert log["uptime_s"] == 0


def test_setting_the_door_to_its_own_state_changes_nothing(board: Board):
    g = board.device.garage
    rev, logged = g.rev, len(g.log)
    g.set_door("closed", 0, "none")
    assert (g.rev, len(g.log)) == (rev, logged)
