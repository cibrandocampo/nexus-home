#!/usr/bin/env python3
"""Converts a sketch .bin into the .ota file the UNO R4 WiFi module downloads and flashes.

Format (as Arduino's bin2ota.py and the module's decoder, Arduino_ESP32_OTA):
  uint32 LE  length  = bytes from offset 8 to the end
  uint32 LE  crc32   = CRC-32 (zlib) of those same bytes
  uint32 LE  magic   = 0x23411002 (UNO R4 WiFi)
  8 bytes    version = 00 00 00 00 00 00 00 40 (as bin2ota.py writes it)
  ...        payload = LZSS (EI=11, EJ=4, ring of 2048 bytes, MSB-first bits,
                       flag 1 = literal byte, flag 0 = 11-bit ring position + 4-bit length-2)

The module always LZSS-decodes the payload. This script decodes its own output with an independent
decoder and refuses to write the file unless it gives back the exact input.

Usage: make_ota.py input.bin output.ota
"""
import struct
import sys
import zlib

EI, EJ = 11, 4
N = 1 << EI          # ring size
F = (1 << EJ) + 1    # longest match (17)
MIN_MATCH = 3        # shorter matches are not worth it
MAX_DIST = N - F     # never reference bytes the decoder may have overwritten
MAGIC = 0x23411002


class BitWriter:
    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.n = 0

    def put(self, value, bits):
        for i in range(bits - 1, -1, -1):
            self.acc = (self.acc << 1) | ((value >> i) & 1)
            self.n += 1
            if self.n == 8:
                self.out.append(self.acc)
                self.acc = self.n = 0

    def flush(self):
        if self.n:
            self.out.append(self.acc << (8 - self.n))  # zero padding: too short for a reference
            self.acc = self.n = 0
        return bytes(self.out)


def encode(data):
    w = BitWriter()
    heads = {}  # 3-byte key -> recent offsets (newest last)
    p = 0
    size = len(data)
    while p < size:
        best_len, best_pos = 0, 0
        if p + MIN_MATCH <= size:
            for s in reversed(heads.get(data[p:p + 3], ())):
                if p - s > MAX_DIST:
                    break
                n = 0
                while n < F and p + n < size and data[s + n] == data[p + n]:
                    n += 1
                if n > best_len:
                    best_len, best_pos = n, s
                    if n == F:
                        break
        step = best_len if best_len >= MIN_MATCH else 1
        if step > 1:
            ring = (N - F + best_pos) & (N - 1)  # ring index where that byte was written
            w.put(0, 1)
            w.put(ring, EI)
            w.put(best_len - 2, EJ)
        else:
            w.put(1, 1)
            w.put(data[p], 8)
        for q in range(p, p + step):
            if q + 3 <= size:
                lst = heads.setdefault(data[q:q + 3], [])
                lst.append(q)
                if len(lst) > 32:
                    del lst[0]
        p += step
    return w.flush()


def decode(payload):
    """Independent decoder written from the module's algorithm (Okumura's lzss.c)."""
    ring = bytearray(b" " * N)
    r = N - F
    out = bytearray()
    bits = len(payload) * 8
    pos = 0

    def get(n):
        nonlocal pos
        v = 0
        for _ in range(n):
            v = (v << 1) | ((payload[pos >> 3] >> (7 - (pos & 7))) & 1)
            pos += 1
        return v

    while pos < bits:
        flag = get(1)
        if flag:
            if bits - pos < 8:
                break
            c = get(8)
            out.append(c)
            ring[r] = c
            r = (r + 1) & (N - 1)
        else:
            if bits - pos < EI + EJ:
                break
            i = get(EI)
            j = get(EJ)
            for k in range(j + 2):
                c = ring[(i + k) & (N - 1)]
                out.append(c)
                ring[r] = c
                r = (r + 1) & (N - 1)
    return bytes(out)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    image = open(sys.argv[1], "rb").read()
    payload = encode(image)
    if decode(payload) != image:
        sys.exit("internal error: the LZSS stream does not decode back to the input")
    body = struct.pack("<I", MAGIC) + bytes([0, 0, 0, 0, 0, 0, 0, 0x40]) + payload
    with open(sys.argv[2], "wb") as f:
        f.write(struct.pack("<II", len(body), zlib.crc32(body) & 0xFFFFFFFF) + body)
    print(f"{sys.argv[2]}: {len(image)} -> {len(body) + 8} bytes")


if __name__ == "__main__":
    main()
