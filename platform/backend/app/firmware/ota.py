"""The UNO R4 WiFi module's .ota format.

Ported from devices/garage-iot-controller/tools/make_ota.py.

Format (Arduino's bin2ota.py and the module's decoder, Arduino_ESP32_OTA):
  uint32 LE  length  = bytes from offset 8 to the end
  uint32 LE  crc32   = CRC-32 (zlib) of those same bytes
  uint32 LE  magic   = 0x23411002 (UNO R4 WiFi)
  8 bytes    version = 00 00 00 00 00 00 00 40 (as bin2ota.py writes it)
  ...        payload = LZSS (EI=11, EJ=4, ring of 2048 bytes, MSB-first bits,
                       flag 1 = literal byte, flag 0 = 11-bit ring position + 4-bit length-2)

`encode` gives the same bytes as the tool (tests compare them) and refuses an output that does not
decode back to its input. CPU-bound: call it from a thread.
"""

import struct
import zlib

from app.core.errors import AppError

EI, EJ = 11, 4
N = 1 << EI  # ring size
F = (1 << EJ) + 1  # longest match (17)
MIN_MATCH = 3  # shorter matches are not worth it
MAX_DIST = N - F  # never reference bytes the decoder may have overwritten
MAGIC = 0x23411002
VERSION_BYTES = bytes([0, 0, 0, 0, 0, 0, 0, 0x40])
HEADER = 8 + 4 + len(VERSION_BYTES)

INVALID = AppError(400, "invalid_firmware", "Not a firmware file for this device")


class _BitWriter:
    def __init__(self) -> None:
        self.out = bytearray()
        self.acc = 0
        self.n = 0

    def put(self, value: int, bits: int) -> None:
        for i in range(bits - 1, -1, -1):
            self.acc = (self.acc << 1) | ((value >> i) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.acc)
                self.acc = self.n = 0

    def flush(self) -> bytes:
        if self.n:
            self.out.append(self.acc << (8 - self.n))  # zero padding: too short for a reference
            self.acc = self.n = 0
        return bytes(self.out)


def _longest(data: bytes, p: int, candidates: list[int]) -> tuple[int, int]:
    best_len, best_pos = 0, 0
    for s in reversed(candidates):
        if p - s > MAX_DIST:
            break
        n = 0
        while n < F and p + n < len(data) and data[s + n] == data[p + n]:
            n += 1
        if n > best_len:
            best_len, best_pos = n, s
            if n == F:
                break
    return best_len, best_pos


def compress(data: bytes) -> bytes:
    """The LZSS payload, exactly as make_ota.py writes it."""
    w = _BitWriter()
    heads: dict[bytes, list[int]] = {}  # 3-byte key -> recent offsets (newest last)
    p = 0
    size = len(data)
    while p < size:
        best_len, best_pos = 0, 0
        if p + MIN_MATCH <= size:
            best_len, best_pos = _longest(data, p, heads.get(data[p : p + 3], []))
        step = best_len if best_len >= MIN_MATCH else 1
        if step > 1:
            w.put(0, 1)
            w.put((N - F + best_pos) & (N - 1), EI)  # ring index where that byte was written
            w.put(best_len - 2, EJ)
        else:
            w.put(1, 1)
            w.put(data[p], 8)
        for q in range(p, p + step):
            if q + 3 <= size:
                recent = heads.setdefault(data[q : q + 3], [])
                recent.append(q)
                if len(recent) > 32:
                    del recent[0]
        p += step
    return w.flush()


def decompress(payload: bytes) -> bytes:
    """Independent decoder, from the module's algorithm (Okumura's lzss.c)."""
    ring = bytearray(b" " * N)
    r = N - F
    out = bytearray()
    bits = len(payload) * 8
    pos = 0

    def get(n: int) -> int:
        nonlocal pos
        v = 0
        for _ in range(n):
            v = (v << 1) | ((payload[pos >> 3] >> (7 - (pos & 7))) & 1)
            pos += 1
        return v

    while pos < bits:
        if get(1):
            if bits - pos < 8:
                break
            c = get(8)
            out.append(c)
            ring[r] = c
            r = (r + 1) & (N - 1)
        else:
            if bits - pos < EI + EJ:
                break
            i, j = get(EI), get(EJ)
            for k in range(j + 2):
                c = ring[(i + k) & (N - 1)]
                out.append(c)
                ring[r] = c
                r = (r + 1) & (N - 1)
    return bytes(out)


def encode(image: bytes) -> bytes:
    """A .bin image as the .ota file the module downloads."""
    if not image:
        raise INVALID
    payload = compress(image)
    if decompress(payload) != image:  # pragma: no cover - the encoder's own guarantee
        raise RuntimeError("the LZSS stream does not decode back to the input")
    body = struct.pack("<I", MAGIC) + VERSION_BYTES + payload
    return struct.pack("<II", len(body), zlib.crc32(body) & 0xFFFFFFFF) + body


def check(ota: bytes) -> None:
    """What the module checks before flashing: length, CRC and magic (else `invalid_firmware`)."""
    if len(ota) <= HEADER:
        raise INVALID
    length, crc = struct.unpack_from("<II", ota)
    body = ota[8:]
    if length != len(body) or zlib.crc32(body) & 0xFFFFFFFF != crc:
        raise INVALID
    if struct.unpack_from("<I", body)[0] != MAGIC:
        raise INVALID


def decode(ota: bytes) -> bytes:
    """The .bin image inside a checked .ota file."""
    check(ota)
    return decompress(ota[HEADER:])
