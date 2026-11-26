import logging
import os
import uuid
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import aiosmtplib
import httpx
import pytest
from jinja2 import UndefinedError

from app.core.config import get_settings
from app.emails import sender

CONTEXT = {"code": "482913", "minutes": 10, "first_name": "Ana"}

SUBJECTS = {
    ("login_code", "en"): "482913 is your Test App sign-in code",
    ("login_code", "es"): "482913 es tu código para entrar en Test App",
    ("login_code", "gl"): "482913 é o teu código para entrar en Test App",
    ("welcome_signup", "en"): "Welcome to Test App: your code is 482913",
    ("welcome_signup", "es"): "Te damos la bienvenida a Test App: tu código es 482913",
    ("welcome_signup", "gl"): "Dámosche a benvida a Test App: o teu código é 482913",
}


@pytest.fixture(autouse=True)
def email_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "app_name", "Test App")
    monkeypatch.setattr(settings, "site_url", "https://app.example.com")
    monkeypatch.setattr(settings, "email_from", "Test App <no-reply@example.com>")
    monkeypatch.setattr(settings, "email_backend", "memory")
    sender.outbox.clear()
    return settings


@pytest.mark.parametrize(("template", "lang"), list(SUBJECTS))
def test_each_template_renders_in_each_language(template, lang):
    subject, text, html = sender.render(template, lang, CONTEXT)

    assert subject == SUBJECTS[(template, lang)]
    assert "482913" in text
    assert "482913" in html
    assert "10" in text
    assert f'<html lang="{lang}">' in html
    assert 'src="cid:logo"' in html
    assert "https://app.example.com" in text


def test_unknown_language_falls_back_to_english():
    subject, _, _ = sender.render("login_code", "fr", CONTEXT)

    assert subject == SUBJECTS[("login_code", "en")]


@pytest.mark.parametrize(
    ("lang", "minutes", "expected"),
    [
        ("en", 1, "1 minute."),
        ("en", 10, "10 minutes."),
        ("es", 1, "1 minuto."),
        ("gl", 5, "5 minutos."),
    ],
)
def test_minutes_agree_in_number(lang, minutes, expected):
    _, text, html = sender.render("login_code", lang, {**CONTEXT, "minutes": minutes})

    assert expected in text
    assert expected in html


@pytest.mark.parametrize(
    ("lang", "greeting"), [("en", "Hello, Ana,"), ("es", "Hola, Ana:"), ("gl", "Ola, Ana:")]
)
def test_greeting_separates_the_name_with_a_comma(lang, greeting):
    _, text, _ = sender.render("login_code", lang, CONTEXT)

    assert text.startswith(greeting)


@pytest.mark.parametrize(
    ("lang", "greeting"), [("en", "Hello,\n"), ("es", "Hola:\n"), ("gl", "Ola:\n")]
)
def test_greeting_without_a_name(lang, greeting):
    _, text, _ = sender.render("login_code", lang, {**CONTEXT, "first_name": ""})

    assert text.startswith(greeting)


def test_html_body_escapes_user_data_and_text_body_keeps_it():
    context = {**CONTEXT, "first_name": "<script>x</script>"}

    _, text, html = sender.render("login_code", "en", context)

    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "<script>x</script>" in text


def test_missing_context_value_is_an_error():
    with pytest.raises(UndefinedError, match="code"):
        sender.render("login_code", "en", {"minutes": 10, "first_name": ""})


async def test_memory_backend_keeps_a_multipart_message_with_the_inline_logo():
    await sender.send_email("ana@example.com", "login_code", "es", CONTEXT)

    [message] = sender.outbox
    assert message["To"] == "ana@example.com"
    assert message["From"] == "Test App <no-reply@example.com>"
    assert message["Subject"] == SUBJECTS[("login_code", "es")]
    text_part, html_part = message.get_payload()
    assert text_part.get_content_type() == "text/plain"
    assert html_part.get_content_type() == "multipart/related"
    html, logo = html_part.get_payload()
    assert html.get_content_type() == "text/html"
    assert logo.get_content_type() == "image/png"
    assert logo["Content-ID"] == "<logo>"
    assert logo.get_content_disposition() == "inline"
    sent = parsedate_to_datetime(message["Date"])
    assert sent.utcoffset() == timedelta(0)
    assert abs(datetime.now(UTC) - sent) < timedelta(minutes=1)
    assert message["Message-ID"].endswith("@example.com>")


@pytest.mark.parametrize(
    ("mode", "use_tls", "start_tls"),
    [("none", False, False), ("starttls", False, True), ("ssl", True, False)],
)
async def test_smtp_security_mode_maps_to_aiosmtplib_options(
    email_settings, monkeypatch, mode, use_tls, start_tls
):
    calls = []

    async def fake_send(message, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(email_settings, "email_backend", "smtp")
    monkeypatch.setattr(email_settings, "smtp_tls", mode)
    monkeypatch.setattr(email_settings, "smtp_user", "mailer")
    monkeypatch.setattr(email_settings, "smtp_password", "secret")
    monkeypatch.setattr(sender.aiosmtplib, "send", fake_send)

    await sender.send_email("ana@example.com", "login_code", "en", CONTEXT)

    [kwargs] = calls
    assert (kwargs["use_tls"], kwargs["start_tls"]) == (use_tls, start_tls)
    assert (kwargs["username"], kwargs["password"]) == ("mailer", "secret")


async def test_smtp_failure_is_logged_and_raised(email_settings, monkeypatch, caplog):
    monkeypatch.setattr(email_settings, "email_backend", "smtp")
    monkeypatch.setattr(email_settings, "smtp_host", "127.0.0.1")
    monkeypatch.setattr(email_settings, "smtp_port", 1)
    monkeypatch.setattr(email_settings, "smtp_tls", "none")
    monkeypatch.setattr(email_settings, "smtp_timeout_seconds", 2)

    with (
        caplog.at_level(logging.ERROR, logger="app.emails.sender"),
        pytest.raises((aiosmtplib.SMTPException, OSError)),
    ):
        await sender.send_email("ana@example.com", "login_code", "en", CONTEXT)

    assert "Sending the login_code email failed" in caplog.text
    assert "ana@example.com" not in caplog.text


async def test_message_is_delivered_to_mailpit(email_settings, monkeypatch):
    """Integration: real SMTP delivery to the dev/CI Mailpit, found through its API."""
    api = os.environ["MAILPIT_API_URL"]  # set by the dev and CI compose files
    monkeypatch.setattr(email_settings, "email_backend", "smtp")
    monkeypatch.setattr(email_settings, "smtp_host", os.environ["MAILPIT_SMTP_HOST"])
    monkeypatch.setattr(email_settings, "smtp_port", 1025)
    monkeypatch.setattr(email_settings, "smtp_tls", "none")
    to = f"mailpit-{uuid.uuid4().hex[:8]}@example.com"

    await sender.send_email(to, "welcome_signup", "gl", CONTEXT)

    async with httpx.AsyncClient(base_url=api) as http:
        found = (await http.get("/api/v1/search", params={"query": f"to:{to}"})).json()
        [summary] = found["messages"]
        detail = (await http.get(f"/api/v1/message/{summary['ID']}")).json()
    assert detail["Subject"] == SUBJECTS[("welcome_signup", "gl")]
    assert "482913" in detail["Text"]
    assert detail["Attachments"] == []
    assert [part["ContentType"] for part in detail["Inline"]] == ["image/png"]
