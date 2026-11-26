"""Transactional emails: Jinja2 templates per language, text + HTML with an inline logo, SMTP."""

import logging
from email.message import EmailMessage
from email.utils import formatdate, make_msgid, parseaddr
from pathlib import Path

import aiosmtplib
from jinja2 import Environment, FileSystemLoader, StrictUndefined, select_autoescape

from app.core.config import get_settings

log = logging.getLogger(__name__)

TEMPLATES = Path(__file__).parent / "templates"
LOGO = Path(__file__).parent / "assets" / "logo.png"
LANGUAGES = ("en", "es", "gl")

_env = Environment(
    loader=FileSystemLoader(TEMPLATES),
    autoescape=select_autoescape(enabled_extensions=("html",), default_for_string=False),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
)

# Messages kept by the "memory" backend (tests and local experiments).
outbox: list[EmailMessage] = []


def render(template: str, lang: str, context: dict) -> tuple[str, str, str]:
    """Return (subject, text, html) for a template in a language (unknown languages use en)."""
    settings = get_settings()
    lang = lang if lang in LANGUAGES else "en"
    ctx = {"app_name": settings.app_name, "site_url": settings.site_url, "lang": lang, **context}
    subject = _env.get_template(f"{template}/{lang}.subject.txt").render(ctx).strip()
    text = _env.get_template(f"{template}/{lang}.body.txt").render(ctx)
    html = _env.get_template(f"{template}/{lang}.body.html").render(ctx)
    return subject, text, html


def build_message(to: str, template: str, lang: str, context: dict) -> EmailMessage:
    subject, text, html = render(template, lang, context)
    sender = get_settings().email_from
    domain = parseaddr(sender)[1].rpartition("@")[2] or None
    message = EmailMessage()
    message["From"] = sender
    message["To"] = to
    message["Subject"] = subject
    message["Date"] = formatdate(localtime=False, usegmt=True)
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(text)
    message.add_alternative(html, subtype="html")
    html_part = message.get_payload()[1]
    html_part.add_related(
        LOGO.read_bytes(), "image", "png", cid="<logo>", disposition="inline", filename="logo.png"
    )
    return message


async def send_email(to: str, template: str, lang: str, context: dict) -> None:
    """Render and send. Raises aiosmtplib.SMTPException (or OSError) when sending fails."""
    settings = get_settings()
    message = build_message(to, template, lang, context)
    if settings.email_backend == "memory":
        outbox.append(message)
        return
    try:
        await aiosmtplib.send(
            message,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_user or None,
            password=settings.smtp_password or None,
            use_tls=settings.smtp_tls == "ssl",
            start_tls=settings.smtp_tls == "starttls",
            timeout=settings.smtp_timeout_seconds,
        )
    except (aiosmtplib.SMTPException, OSError) as exc:
        # SMTP errors can quote the recipient address: log the error type, not its text.
        log.error("Sending the %s email failed: %s", template, type(exc).__name__)
        raise
