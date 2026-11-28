"""The platform's .ota converter against the board tools' own output.

Fixtures (tests/fixtures/firmware): `garage-head.bin` is the first 32 KB of a real build
(`dist/garage-2.0.6.bin`), `synthetic.bin` mixes long repeats and random bytes. The `.ota` files
next to them were written by `devices/garage-iot-controller/tools/make_ota.py`
(in python:3.14-slim):

    python -I devices/garage-iot-controller/tools/make_ota.py <name>.bin <name>.ota
"""

import struct
import time
import zlib
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.firmware import ota

FIXTURES = Path(__file__).parent / "fixtures" / "firmware"


@pytest.mark.parametrize("name", ["garage-head", "synthetic"])
def test_the_same_bytes_as_the_board_tool(name):
    image = (FIXTURES / f"{name}.bin").read_bytes()

    assert ota.encode(image) == (FIXTURES / f"{name}.ota").read_bytes()


@pytest.mark.parametrize("name", ["garage-head", "synthetic"])
def test_a_tool_made_file_decodes_to_its_image(name):
    assert (
        ota.decode((FIXTURES / f"{name}.ota").read_bytes())
        == (FIXTURES / f"{name}.bin").read_bytes()
    )


def test_round_trip_of_edge_inputs():
    for image in (b"x", b"ab", bytes(17), bytes(range(256)) * 9, b"\xff" * 5000):
        assert ota.decode(ota.encode(image)) == image


def test_an_empty_image_is_not_firmware():
    with pytest.raises(AppError) as caught:
        ota.encode(b"")

    assert caught.value.code == "invalid_firmware"


def _broken(transform):
    good = bytearray((FIXTURES / "synthetic.ota").read_bytes())
    transform(good)
    return bytes(good)


def _bad_magic(data):
    body = bytearray(data[8:])
    body[0:4] = struct.pack("<I", 0x12345678)
    data[8:] = body
    data[4:8] = struct.pack("<I", zlib.crc32(bytes(body)) & 0xFFFFFFFF)  # a valid CRC, wrong board


@pytest.mark.parametrize(
    "bad",
    [
        b"",
        b"short",
        _broken(lambda d: d.__setitem__(slice(len(d) - 1, None), b"\x00\x00")),  # longer than said
        (FIXTURES / "synthetic.ota").read_bytes()[:-1],  # cut short
        _broken(lambda d: d.__setitem__(-1, d[-1] ^ 0xFF)),  # CRC mismatch
        _broken(_bad_magic),
        b"<html>not found</html>" * 3,
    ],
)
def test_what_the_module_would_refuse(bad):
    with pytest.raises(AppError) as caught:
        ota.check(bad)

    assert (caught.value.status, caught.value.code) == (400, "invalid_firmware")


def test_a_full_size_image_converts_in_reasonable_time():
    image = (FIXTURES / "garage-head.bin").read_bytes() * 8  # 256 KB, twice a real build

    started = time.perf_counter()
    encoded = ota.encode(image)
    elapsed = time.perf_counter() - started

    assert ota.decode(encoded) == image
    assert elapsed < 10


def test_a_payload_ending_in_a_half_literal_stops_there():
    # Only a hand-made payload reaches it: a literal flag with fewer than 8 bits after it.
    assert ota.decompress(b"\x80") == b""
