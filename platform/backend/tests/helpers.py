"""Helpers shared by the API tests."""

import re

from app.emails import sender


def last_code(to: str) -> str:
    """The 6-digit code of the newest email sent to `to` (memory backend)."""
    messages = [m for m in sender.outbox if m["To"] == to]
    assert messages, f"no email sent to {to}"
    return re.search(r"\b(\d{6})\b", messages[-1]["Subject"]).group(1)


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def cookie_header(response) -> str:
    return response.headers.get("set-cookie", "")
