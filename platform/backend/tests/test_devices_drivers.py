from app.devices.drivers import GARAGE, device_type, driver_for
from app.devices.models import Device
from app.devices.service import client_for, device_token


def test_the_type_is_the_id_prefix():
    assert device_type("garage-3562d4") == "garage"
    assert device_type("sound-00aa11") == "sound"


def test_the_garage_driver_edits_its_settings_but_never_wifi_or_token():
    assert driver_for("garage") is GARAGE
    assert GARAGE.settings_fields == (
        "name",
        "open_s",
        "close_s",
        "light_s",
        "night_level",
        "display",
    )
    assert not any(f.startswith("wifi") or f == "token" for f in GARAGE.settings_fields)


def test_unknown_types_have_no_driver():
    assert driver_for("sound") is None


def test_a_device_without_a_token_gets_a_client_without_one():
    device = Device(host="10.1.3.50", token_encrypted=None)

    assert device_token(device) is None
    assert client_for(device).token is None
    assert device.has_token is False
