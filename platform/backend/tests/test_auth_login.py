from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.auth.models import FailedLogin, LoginCode
from app.auth.router import preferred_language
from app.core.config import get_settings
from app.emails import sender
from app.users.models import AuthMethod, Language, Role, User
from tests.helpers import auth, cookie_header, last_code

PASSWORD = "correct horse battery"


@pytest.fixture
def signup_open(monkeypatch):
    monkeypatch.setattr(get_settings(), "allow_self_signup", True)


async def _user(db, email) -> User:
    db.expire_all()
    return await db.scalar(select(User).where(User.email == email))


async def _start(client, email, **headers):
    return await client.post("/api/auth/login/start", json={"email": email}, headers=headers)


async def _verify(client, email, **secret):
    return await client.post("/api/auth/login/verify", json={"email": email, **secret})


# ---- config ----


@pytest.mark.parametrize("enabled", [True, False])
async def test_config_reports_whether_sign_up_is_open(client, monkeypatch, enabled):
    monkeypatch.setattr(get_settings(), "allow_self_signup", enabled)

    response = await client.get("/api/auth/config")

    assert response.json() == {"allow_self_signup": enabled}


# ---- login/start ----


async def test_unknown_email_with_sign_up_closed_is_not_found(client):
    response = await _start(client, "nobody@example.com")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"
    assert sender.outbox == []


async def test_sign_up_creates_a_user_without_permissions_and_sends_the_welcome_code(
    client, db, signup_open
):
    response = await _start(
        client, "New.Person@Example.com", **{"Accept-Language": "gl-ES,es;q=0.8"}
    )

    assert response.json() == {"method": "otp"}
    user = await _user(db, "new.person@example.com")
    assert user.role is Role.none
    assert user.auth_method is AuthMethod.otp
    assert user.is_active
    assert user.email_verified_at is None
    assert user.language is Language.gl
    [message] = sender.outbox
    assert message["Subject"].startswith("Dámosche a benvida")


async def test_sign_up_with_a_disposable_email_is_refused(client, db, signup_open):
    response = await _start(client, "someone@sub.mailinator.com")

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "disposable_email"
    assert await _user(db, "someone@sub.mailinator.com") is None


async def test_existing_otp_user_gets_a_login_code(client, make_user):
    await make_user(
        "ana@example.com",
        auth_method=AuthMethod.otp,
        password=None,
        email_verified_at=datetime.now(UTC),
        language=Language.es,
    )

    response = await _start(client, "ana@example.com")

    assert response.json() == {"method": "otp"}
    [message] = sender.outbox
    assert " es tu código para entrar en " in message["Subject"]


async def test_unconfirmed_sign_up_asking_again_gets_the_welcome_email(client, db, signup_open):
    await _start(client, "new@example.com")

    await _start(client, "new@example.com")

    assert [m["Subject"].startswith("Welcome") for m in sender.outbox] == [True, True]


async def test_password_user_is_told_to_use_the_password_and_no_email_is_sent(client, make_user):
    await make_user("ana@example.com")

    response = await _start(client, "ana@example.com")

    assert response.json() == {"method": "password"}
    assert sender.outbox == []


async def test_disabled_account_cannot_start_a_login(client, make_user):
    await make_user("ana@example.com", is_active=False)

    response = await _start(client, "ana@example.com")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "account_disabled"


async def test_invalid_email_is_a_validation_error(client):
    response = await _start(client, "not-an-email")

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("es-ES,es;q=0.9,en;q=0.8", Language.es),
        ("fr-FR,gl;q=0.5,es;q=0.7", Language.es),
        ("fr, de", Language.en),
        ("gl;q=bad, es;q=0.1", Language.es),
        (None, Language.en),
    ],
)
def test_preferred_language_picks_the_best_supported_one(header, expected):
    assert preferred_language(header) is expected


# ---- login/verify: code ----


async def test_code_login_confirms_a_sign_up_and_returns_a_session(client, db, signup_open):
    await _start(client, "new@example.com")

    response = await _verify(client, "new@example.com", code=last_code("new@example.com"))

    assert response.status_code == 200
    body = response.json()
    assert body["is_new"] is True
    assert body["user"]["email"] == "new@example.com"
    assert body["user"]["role"] == "none"
    assert body["access_token"]
    assert "refresh_token=" in cookie_header(response)
    user = await _user(db, "new@example.com")
    assert user.email_verified_at is not None
    assert user.last_login_at is not None


async def test_user_with_a_name_is_not_new(client, make_user):
    await make_user("ana@example.com", first_name="Ana")

    response = await _verify(client, "ana@example.com", password=PASSWORD)

    assert response.json()["is_new"] is False


async def test_wrong_code_is_refused(client, signup_open):
    await _start(client, "new@example.com")
    code = last_code("new@example.com")
    wrong = "000000" if code != "000000" else "111111"

    response = await _verify(client, "new@example.com", code=wrong)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_a_code_works_only_once(client, signup_open):
    await _start(client, "new@example.com")
    code = last_code("new@example.com")
    await _verify(client, "new@example.com", code=code)

    response = await _verify(client, "new@example.com", code=code)

    assert response.status_code == 400


async def test_expired_code_is_refused(client, db, signup_open):
    await _start(client, "new@example.com")
    await db.execute(update(LoginCode).values(expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    await db.commit()

    response = await _verify(client, "new@example.com", code=last_code("new@example.com"))

    assert response.status_code == 400


async def test_only_the_newest_code_counts(client, signup_open):
    await _start(client, "new@example.com")
    first = last_code("new@example.com")
    await _start(client, "new@example.com")
    second = last_code("new@example.com")

    if first != second:
        assert (await _verify(client, "new@example.com", code=first)).status_code == 400
    assert (await _verify(client, "new@example.com", code=second)).status_code == 200


async def test_code_is_refused_after_too_many_wrong_attempts(client, signup_open):
    await _start(client, "new@example.com")
    code = last_code("new@example.com")
    wrong = "000000" if code != "000000" else "111111"
    for _ in range(5):
        await _verify(client, "new@example.com", code=wrong)

    response = await _verify(client, "new@example.com", code=code)

    assert response.status_code == 400


async def test_code_for_a_password_account_is_a_method_mismatch(client, make_user):
    await make_user("ana@example.com")

    response = await _verify(client, "ana@example.com", code="123456")

    assert response.json()["error"]["code"] == "method_mismatch"


async def test_unknown_email_on_verify_is_invalid_credentials(client):
    response = await _verify(client, "nobody@example.com", code="123456")

    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_disabled_account_cannot_verify(client, make_user):
    await make_user("ana@example.com", is_active=False)

    response = await _verify(client, "ana@example.com", password=PASSWORD)

    assert response.json()["error"]["code"] == "account_disabled"


@pytest.mark.parametrize(
    "secret",
    [{"code": "1" * 13}, {"password": "x" * 1025}, {"password": "x\x00"}, {"code": "\x00"}],
)
async def test_overlong_code_or_password_is_a_validation_error(client, make_user, secret):
    await make_user("ana@example.com")

    response = await _verify(client, "ana@example.com", **secret)

    assert response.status_code == 422


@pytest.mark.parametrize("secrets", [{}, {"code": "123456", "password": PASSWORD}])
async def test_verify_needs_exactly_one_of_code_and_password(client, make_user, secrets):
    await make_user("ana@example.com")

    response = await _verify(client, "ana@example.com", **secrets)

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


# ---- login/verify: password ----


async def test_password_login_returns_a_session(client, make_user):
    await make_user("ana@example.com")

    response = await _verify(client, "ANA@example.com", password=PASSWORD)

    assert response.status_code == 200
    assert (await client.get("/api/auth/me", headers=auth(response.json()["access_token"]))).json()[
        "email"
    ] == "ana@example.com"


async def test_wrong_password_is_recorded(client, db, make_user):
    user = await make_user("ana@example.com")

    response = await _verify(client, "ana@example.com", password="wrong password!")

    assert response.json()["error"]["code"] == "invalid_credentials"
    failures = (await db.scalars(select(FailedLogin).where(FailedLogin.user_id == user.id))).all()
    assert [f.ip for f in failures] == ["127.0.0.1"]


async def test_password_for_an_otp_account_is_a_method_mismatch(client, make_user):
    await make_user("ana@example.com", auth_method=AuthMethod.otp, password=None)

    response = await _verify(client, "ana@example.com", password=PASSWORD)

    assert response.json()["error"]["code"] == "method_mismatch"


async def test_five_wrong_passwords_lock_the_account_even_with_the_right_one(client, make_user):
    await make_user("ana@example.com")
    for _ in range(5):
        await _verify(client, "ana@example.com", password="wrong password!")

    response = await _verify(client, "ana@example.com", password=PASSWORD)

    assert response.status_code == 429
    assert response.json()["error"]["code"] == "locked"


async def test_lock_ends_after_the_window(client, db, make_user):
    await make_user("ana@example.com")
    for _ in range(5):
        await _verify(client, "ana@example.com", password="wrong password!")
    await db.execute(
        update(FailedLogin).values(created_at=datetime.now(UTC) - timedelta(minutes=16))
    )
    await db.commit()

    response = await _verify(client, "ana@example.com", password=PASSWORD)

    assert response.status_code == 200


async def test_successful_login_clears_failed_attempts(client, db, make_user):
    user = await make_user("ana@example.com")
    for _ in range(4):
        await _verify(client, "ana@example.com", password="wrong password!")

    await _verify(client, "ana@example.com", password=PASSWORD)

    remaining = await db.scalars(select(FailedLogin).where(FailedLogin.user_id == user.id))
    assert remaining.all() == []
