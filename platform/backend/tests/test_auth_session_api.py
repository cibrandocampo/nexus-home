from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.auth.models import RefreshToken
from app.users.models import AuthMethod, Language, Theme
from tests.helpers import auth, cookie_header

PASSWORD = "correct horse battery"


async def _login(client, make_user, email="ana@example.com", **fields):
    await make_user(email, **fields)
    response = await client.post(
        "/api/auth/login/verify", json={"email": email, "password": PASSWORD}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


async def test_refresh_with_the_cookie_returns_a_new_session(client, make_user):
    await _login(client, make_user)
    old_cookie = client.cookies.get("refresh_token", path="/api/auth")

    response = await client.post("/api/auth/refresh")

    assert response.status_code == 200
    assert response.json()["user"]["email"] == "ana@example.com"
    assert client.cookies.get("refresh_token", path="/api/auth") != old_cookie


async def test_refresh_without_a_cookie_is_unauthorized_and_clears_it(client):
    response = await client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert "Max-Age=0" in cookie_header(response)


async def test_refresh_with_a_just_rotated_cookie_keeps_the_session(client, make_user):
    await _login(client, make_user)
    old = client.cookies.get("refresh_token", path="/api/auth")
    await client.post("/api/auth/refresh")
    new = client.cookies.get("refresh_token", path="/api/auth")

    client.cookies.set("refresh_token", old, path="/api/auth")
    raced = await client.post("/api/auth/refresh")

    assert raced.status_code == 401
    assert raced.json()["error"]["code"] == "refresh_in_progress"
    assert "set-cookie" not in raced.headers
    client.cookies.set("refresh_token", new, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 200


async def test_logout_ends_the_session_and_clears_the_cookie(client, make_user):
    await _login(client, make_user)
    raw = client.cookies.get("refresh_token", path="/api/auth")

    response = await client.post("/api/auth/logout")

    assert response.status_code == 204
    assert "Max-Age=0" in cookie_header(response)
    client.cookies.set("refresh_token", raw, path="/api/auth")
    assert (await client.post("/api/auth/refresh")).status_code == 401


async def test_logout_with_an_old_cookie_ends_the_session_it_led_to(client, db, make_user):
    await _login(client, make_user)
    old = client.cookies.get("refresh_token", path="/api/auth")
    await client.post("/api/auth/refresh")

    client.cookies.set("refresh_token", old, path="/api/auth")
    await client.post("/api/auth/logout")

    live = await db.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None)))
    assert live.all() == []


async def test_logout_without_a_cookie_still_answers_no_content(client):
    assert (await client.post("/api/auth/logout")).status_code == 204


async def test_me_requires_authentication(client):
    response = await client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_returns_the_profile(client, make_user):
    token = await _login(client, make_user, first_name="Ana")

    body = (await client.get("/api/auth/me", headers=auth(token))).json()

    assert body["email"] == "ana@example.com"
    assert body["first_name"] == "Ana"
    assert body["role"] == "user"
    assert body["timezone"] == "UTC"
    assert "password_hash" not in body


async def test_profile_update_changes_name_language_theme_and_timezone(client, make_user):
    token = await _login(client, make_user)

    response = await client.patch(
        "/api/auth/me",
        headers=auth(token),
        json={
            "first_name": "  Ana ",
            "last_name": "Pérez",
            "language": "gl",
            "theme": "dark",
            "timezone": "Europe/Madrid",
        },
    )

    body = response.json()
    assert (body["first_name"], body["last_name"]) == ("Ana", "Pérez")
    assert (body["language"], body["theme"]) == (Language.gl.value, Theme.dark.value)
    assert body["timezone"] == "Europe/Madrid"


@pytest.mark.parametrize("zone", ["Asia/Kolkata", "Asia/Calcutta", "Europe/Kiev", "UTC"])
async def test_profile_update_accepts_the_zone_names_browsers_report(client, make_user, zone):
    # Browsers still report some zones by their old IANA names; the server must accept them all.
    token = await _login(client, make_user)

    response = await client.patch("/api/auth/me", headers=auth(token), json={"timezone": zone})

    assert response.status_code == 200
    assert response.json()["timezone"] == zone


@pytest.mark.parametrize(
    "payload",
    [
        {"first_name": "   "},
        {"first_name": "A\x00"},
        {"language": "fr"},
        {"timezone": "Mars/Olympus_Mons"},
        {"role": "admin"},
        {"email": "x@example.com"},
    ],
)
async def test_profile_update_rejects_blank_names_unknown_values_and_other_fields(
    client, make_user, payload
):
    token = await _login(client, make_user)

    response = await client.patch("/api/auth/me", headers=auth(token), json=payload)

    assert response.status_code == 422


async def test_profile_update_rejects_explicit_null(client, make_user):
    token = await _login(client, make_user)

    response = await client.patch("/api/auth/me", headers=auth(token), json={"first_name": None})

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_request"


async def test_change_password_needs_the_current_one(client, make_user):
    token = await _login(client, make_user)

    response = await client.post(
        "/api/auth/change-password",
        headers=auth(token),
        json={"current_password": "wrong password!", "new_password": "a new long password"},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_change_password_applies_the_password_rules(client, make_user):
    token = await _login(client, make_user)

    response = await client.post(
        "/api/auth/change-password",
        headers=auth(token),
        json={"current_password": PASSWORD, "new_password": "short"},
    )

    assert response.json()["error"]["code"] == "weak_password"


async def test_change_password_ends_other_sessions_and_keeps_this_one(client, db, make_user):
    token = await _login(client, make_user)
    other = await client.post(
        "/api/auth/login/verify", json={"email": "ana@example.com", "password": PASSWORD}
    )
    assert other.status_code == 200

    response = await client.post(
        "/api/auth/change-password",
        headers=auth(token),
        json={"current_password": PASSWORD, "new_password": "a new long password"},
    )

    assert response.status_code == 200
    live = (await db.scalars(select(RefreshToken).where(RefreshToken.revoked_at.is_(None)))).all()
    assert len(live) == 1
    assert (await client.post("/api/auth/refresh")).status_code == 200
    login = await client.post(
        "/api/auth/login/verify",
        json={"email": "ana@example.com", "password": "a new long password"},
    )
    assert login.status_code == 200


async def test_otp_user_can_set_a_first_password_and_switches_to_password_login(
    client, db, make_user, monkeypatch
):
    user = await make_user(
        "ana@example.com",
        auth_method=AuthMethod.otp,
        password=None,
        email_verified_at=datetime.now(UTC),
    )
    from app.core.security import create_access_token

    response = await client.post(
        "/api/auth/change-password",
        headers=auth(create_access_token(user.id, "user")),
        json={"new_password": "a new long password"},
    )

    assert response.status_code == 200
    assert response.json()["user"]["auth_method"] == "password"
    start = await client.post("/api/auth/login/start", json={"email": "ana@example.com"})
    assert start.json() == {"method": "password"}


async def test_expired_refresh_token_clears_the_cookie(client, db, make_user):
    await _login(client, make_user)
    await db.execute(update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(1)))
    await db.commit()

    response = await client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"
    assert "Max-Age=0" in cookie_header(response)
