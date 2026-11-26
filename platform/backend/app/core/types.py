"""Input types shared by request bodies and parameters.

PostgreSQL text cannot hold the NUL character: every user-supplied string goes through these
types so a NUL is a 422 at the boundary instead of a database error.
"""

import functools
import zoneinfo
from typing import Annotated

from fastapi import Path
from pydantic import AfterValidator, StringConstraints

NO_NUL = r"^[^\x00]*$"
# Names are shown to other users: no control characters, zero-width characters or bidirectional
# controls, which could make a name look like something else.
PLAIN_TEXT = r"^[^\x00-\x1f\x7f\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]*$"
MAX_DB_INT = 2_147_483_647  # INTEGER primary keys

Name = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=100, pattern=PLAIN_TEXT),
]
OptionalName = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=100, pattern=PLAIN_TEXT)
]
Secret = Annotated[str, StringConstraints(max_length=1024, pattern=NO_NUL)]
Code = Annotated[str, StringConstraints(max_length=12, pattern=NO_NUL)]
IdPath = Annotated[int, Path(ge=1, le=MAX_DB_INT)]


@functools.cache
def _time_zones() -> frozenset[str]:
    # The system database plus the `tzdata` package (legacy names included); read once, it walks
    # the disk.
    return frozenset(zoneinfo.available_timezones())


def _known_time_zone(value: str) -> str:
    if value not in _time_zones():
        raise ValueError("unknown IANA time zone")
    return value


# An IANA time zone name, e.g. "Europe/Madrid".
TimeZone = Annotated[str, StringConstraints(max_length=64), AfterValidator(_known_time_zone)]
