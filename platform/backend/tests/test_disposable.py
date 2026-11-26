import pytest

from app.auth.disposable import blocked_domains, is_disposable
from app.core.config import get_settings


@pytest.mark.parametrize(
    ("email", "blocked"),
    [
        ("a@mailinator.com", True),
        ("a@deep.sub.mailinator.com", True),
        ("a@MAILINATOR.com", True),
        ("a@gmail.com", False),
        ("a@mailinator.com.example", False),  # only whole domain suffixes count
    ],
)
def test_listed_domains_and_their_subdomains_are_blocked(email, blocked):
    assert is_disposable(email) is blocked


def test_the_synced_list_is_loaded():
    assert len(blocked_domains()) > 1000


def test_extra_and_allowed_domains_from_the_environment(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "disposable_email_extra_domains", "temp.example, Other.example")
    monkeypatch.setattr(settings, "disposable_email_allow_domains", "mailinator.com")
    blocked_domains.cache_clear()

    assert is_disposable("a@temp.example")
    assert is_disposable("a@other.example")
    assert not is_disposable("a@mailinator.com")


def test_blocking_can_be_turned_off(monkeypatch):
    monkeypatch.setattr(get_settings(), "block_disposable_email", False)

    assert not is_disposable("a@mailinator.com")
