"""The firmware's minimal JSON field readers (firmware/json.h), ported byte for byte.

The board does not parse JSON: it looks for `"key":` in the raw body and reads the value there. A
platform client must live with exactly that, so the simulator reads request bodies the same way:
lengths are in bytes (UTF-8 passes through raw), `\\u` escapes above 0x7F are rejected, escaped
control characters are accepted, a number stops at its first non-digit (`30.5` is refused only for
settings, where a `.` right after the digits is checked), and a body that is not JSON at all is just
a body where no key is found.
"""

from enum import Enum

WS = b" \t\r\n"


class Result(Enum):
    MISSING = 0
    OK = 1
    INVALID = 2


def find(body: bytes, key: str) -> int | None:
    """Index of the value after `"key":`, or None (json.h find)."""
    k = key.encode()
    n = len(k)
    p = body.find(b'"')
    while p != -1:
        if body[p + 1 : p + 1 + n] == k and body[p + 1 + n : p + 2 + n] == b'"':
            v = p + n + 2
            while v < len(body) and body[v] in WS:
                v += 1
            if v < len(body) and body[v : v + 1] == b":":
                v += 1
                while v < len(body) and body[v] in WS:
                    v += 1
                return v
        p = body.find(b'"', p + 1)
    return None


ESCAPES = {
    ord('"'): ord('"'),
    ord("\\"): ord("\\"),
    ord("/"): ord("/"),
    ord("n"): 10,
    ord("t"): 9,
    ord("r"): 13,
    ord("b"): 8,
    ord("f"): 12,
}


def string(body: bytes, key: str, size: int) -> tuple[Result, str]:
    """A string value that fits a buffer of `size` bytes, terminator included (json.h str)."""
    p = find(body, key)
    if p is None:
        return Result.MISSING, ""
    if body[p : p + 1] != b'"':
        return Result.INVALID, ""
    p += 1
    out = bytearray()
    while p < len(body) and body[p] != ord('"'):
        c = body[p]
        p += 1
        if c == ord("\\"):
            if p >= len(body):
                return Result.INVALID, ""
            e = body[p]
            p += 1
            if e in ESCAPES:
                c = ESCAPES[e]
            elif e == ord("u"):
                digits = body[p : p + 4]
                p += 4
                try:
                    # strtoul(base 16) as the board; unlike int(), it takes no "_" separators.
                    ok = len(digits) == 4 and b"_" not in digits
                    v = int(digits, 16) if ok else -1
                except ValueError:
                    v = -1
                if v <= 0 or v > 0x7F:
                    return Result.INVALID, ""
                c = v
            else:
                return Result.INVALID, ""
        elif c < 0x20:
            return Result.INVALID, ""
        if len(out) + 1 >= size:  # too long
            return Result.INVALID, ""
        out.append(c)
    if p >= len(body):
        return Result.INVALID, ""
    return Result.OK, out.decode("utf-8", errors="replace")


def flag(body: bytes, key: str) -> tuple[Result, bool]:
    """true / false (json.h flag)."""
    p = find(body, key)
    if p is None:
        return Result.MISSING, False
    if body.startswith(b"true", p):
        return Result.OK, True
    if body.startswith(b"false", p):
        return Result.OK, False
    return Result.INVALID, False


def leading_number(body: bytes, p: int) -> tuple[int | None, int]:
    """strtoul from p: the value (None when no digit) and the index after the digits."""
    end = p
    while end < len(body) and 0x30 <= body[end] <= 0x39:
        end += 1
    return (int(body[p:end]) if end > p else None), end


def number(body: bytes, key: str) -> tuple[Result, int]:
    """A non-negative integer (json.h num): digits, not followed by a `.`, at most 32 bits."""
    p = find(body, key)
    if p is None:
        return Result.MISSING, 0
    value, end = leading_number(body, p)
    if value is None or body[end : end + 1] == b"." or value > 0xFFFFFFFF:
        return Result.INVALID, 0
    return Result.OK, value


def duration(query: str | None, body: bytes) -> int | bool | None:
    """http.cpp findDuration: the seconds, None when not given, False when invalid (> 86400 too).

    The query string wins; in the body the board looks for `"duration"` and reads the digits after
    the spaces and colons that follow (so `30.5` reads as 30).
    """
    if query is not None and "duration=" in query:
        raw = query[query.index("duration=") + 9 :].encode()
        value, _ = leading_number(raw, 0)
    else:
        at = body.find(b'"duration"')
        if at == -1:
            return None
        p = at + 10
        while p < len(body) and body[p : p + 1] in (b" ", b":"):
            p += 1
        value, _ = leading_number(body, p)
    if value is None or value > 86400:
        return False
    return value
