import asyncio

import pytest
from sqlalchemy import delete, select, update

from app.auth import sessions
from app.auth.models import RefreshToken
from app.core.db import get_sessionmaker
from app.core.security import create_access_token, verify_password
from app.users.models import AuthMethod, Role, User
from tests.helpers import auth

PASSWORD = "correct horse battery"


@pytest.fixture
async def admin(make_user):
    return await make_user("admin@example.com", role=Role.admin, first_name="Ada")


@pytest.fixture
def as_admin(admin):
    return auth(create_access_token(admin.id, "admin"))


async def _live_sessions(db, user_id) -> int:
    db.expire_all()
    rows = await db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)
        )
    )
    return len(rows.all())


# ---- access ----


ENDPOINTS = [
    ("get", "/api/users"),
    ("post", "/api/users"),
    ("get", "/api/users/1"),
    ("patch", "/api/users/1"),
    ("post", "/api/users/1/set-password"),
    ("delete", "/api/users/1"),
]


@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
async def test_every_endpoint_requires_authentication(client, method, path):
    response = await client.request(method, path, json={})

    assert response.status_code == 401


@pytest.mark.parametrize("role", [Role.none, Role.user])
@pytest.mark.parametrize(("method", "path"), ENDPOINTS)
async def test_non_admins_are_forbidden_everywhere(client, make_user, role, method, path):
    user = await make_user("someone@example.com", role=role)

    response = await client.request(
        method, path, headers=auth(create_access_token(user.id, role.value)), json={}
    )

    assert response.status_code == 403


# ---- list ----


async def test_list_is_paginated_and_ordered_by_email(client, make_user, as_admin):
    for name in ("carla", "bea", "dani"):
        await make_user(f"{name}@example.com")

    response = await client.get("/api/users", headers=as_admin, params={"page": 2, "size": 2})

    body = response.json()
    assert body["total"] == 4
    assert (body["page"], body["size"]) == (2, 2)
    assert [u["email"] for u in body["items"]] == ["carla@example.com", "dani@example.com"]


async def test_list_searches_email_and_full_name(client, make_user, as_admin):
    await make_user("ana@example.com", first_name="Ana", last_name="Pérez")
    await make_user("luis@sample.org")

    by_name = await client.get("/api/users", headers=as_admin, params={"q": "ana pér"})
    by_email = await client.get("/api/users", headers=as_admin, params={"q": "SAMPLE"})

    assert [u["email"] for u in by_name.json()["items"]] == ["ana@example.com"]
    assert [u["email"] for u in by_email.json()["items"]] == ["luis@sample.org"]


async def test_list_filters_by_role_and_active(client, make_user, as_admin):
    await make_user("pending@example.com", role=Role.none)
    await make_user("off@example.com", is_active=False)

    pending = await client.get("/api/users", headers=as_admin, params={"role": "none"})
    inactive = await client.get("/api/users", headers=as_admin, params={"active": "false"})

    assert [u["email"] for u in pending.json()["items"]] == ["pending@example.com"]
    assert [u["email"] for u in inactive.json()["items"]] == ["off@example.com"]


async def test_search_treats_wildcards_as_text(client, make_user, as_admin):
    await make_user("a_b@example.com")
    await make_user("axb@example.com")
    await make_user("full%done@example.com")

    underscore = await client.get("/api/users", headers=as_admin, params={"q": "a_b"})
    percent = await client.get("/api/users", headers=as_admin, params={"q": "%"})

    assert [u["email"] for u in underscore.json()["items"]] == ["a_b@example.com"]
    assert [u["email"] for u in percent.json()["items"]] == ["full%done@example.com"]


async def test_blank_search_lists_everyone(client, make_user, as_admin):
    await make_user("ana@example.com")

    response = await client.get("/api/users", headers=as_admin, params={"q": "   "})

    assert response.json()["total"] == 2


@pytest.mark.parametrize(
    "params",
    [
        {"page": 0},
        {"page": 100_001},
        {"page": "9" * 30},
        {"size": 101},
        {"role": "owner"},
        {"q": "a\x00b"},
    ],
)
async def test_list_rejects_invalid_parameters(client, as_admin, params):
    response = await client.get("/api/users", headers=as_admin, params=params)

    assert response.status_code == 422


# ---- create ----


async def test_create_otp_user_is_active_and_verified(client, db, as_admin):
    response = await client.post(
        "/api/users",
        headers=as_admin,
        json={"email": " New@Example.com ", "first_name": "New", "role": "user", "language": "gl"},
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["email"], body["role"], body["auth_method"], body["language"]) == (
        "new@example.com",
        "user",
        "otp",
        "gl",
    )
    assert body["is_active"] is True
    user = await db.get(User, body["id"])
    assert user.email_verified_at is not None


async def test_create_password_user_stores_the_hash(client, db, as_admin):
    response = await client.post(
        "/api/users",
        headers=as_admin,
        json={"email": "pw@example.com", "auth_method": "password", "password": PASSWORD},
    )

    user = await db.get(User, response.json()["id"])
    assert user.auth_method is AuthMethod.password
    assert verify_password(PASSWORD, user.password_hash)


async def test_create_password_user_needs_a_valid_password(client, as_admin):
    missing = await client.post(
        "/api/users", headers=as_admin, json={"email": "pw@example.com", "auth_method": "password"}
    )
    weak = await client.post(
        "/api/users",
        headers=as_admin,
        json={"email": "pw@example.com", "auth_method": "password", "password": "short"},
    )

    assert missing.json()["error"]["code"] == "password_required"
    assert weak.json()["error"]["code"] == "weak_password"


async def test_create_otp_user_refuses_a_password(client, as_admin):
    response = await client.post(
        "/api/users", headers=as_admin, json={"email": "otp@example.com", "password": PASSWORD}
    )

    assert response.json()["error"]["code"] == "password_not_allowed"


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("post", "/api/users", {"email": "n@example.com", "first_name": "A\x00"}),
        ("patch", "/api/users/{id}", {"last_name": "\x00"}),
        ("post", "/api/users/{id}/set-password", {"password": "long enough\x00password"}),
    ],
)
async def test_nul_characters_are_rejected_before_the_database(
    client, make_user, as_admin, method, path, body
):
    user = await make_user("ana@example.com")

    response = await client.request(method, path.format(id=user.id), headers=as_admin, json=body)

    assert response.status_code == 422


@pytest.mark.parametrize("user_id", ["0", "2147483648", "9" * 30])
@pytest.mark.parametrize("method", ["get", "patch", "delete"])
async def test_ids_outside_the_column_range_are_rejected(client, as_admin, method, user_id):
    response = await client.request(method, f"/api/users/{user_id}", headers=as_admin, json={})

    assert response.status_code == 422


async def test_create_with_a_taken_email_conflicts(client, make_user, as_admin):
    await make_user("ana@example.com")

    response = await client.post("/api/users", headers=as_admin, json={"email": "ANA@example.com"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "email_taken"


async def test_concurrent_creation_of_one_email_creates_one_user(client, db, as_admin):
    responses = await asyncio.gather(
        *(
            client.post("/api/users", headers=as_admin, json={"email": "race@example.com"})
            for _ in range(5)
        )
    )

    assert sorted(r.status_code for r in responses) == [201, 409, 409, 409, 409]


# ---- get / update ----


async def test_get_returns_one_user_or_404(client, make_user, as_admin):
    user = await make_user("ana@example.com")

    found = await client.get(f"/api/users/{user.id}", headers=as_admin)
    missing = await client.get("/api/users/999999", headers=as_admin)

    assert found.json()["email"] == "ana@example.com"
    assert missing.json()["error"]["code"] == "user_not_found"


async def test_granting_access_to_a_sign_up(client, make_user, as_admin):
    user = await make_user("new@example.com", role=Role.none)

    response = await client.patch(f"/api/users/{user.id}", headers=as_admin, json={"role": "user"})

    assert response.json()["role"] == "user"


async def test_update_names_and_language(client, make_user, as_admin):
    user = await make_user("ana@example.com")

    response = await client.patch(
        f"/api/users/{user.id}",
        headers=as_admin,
        json={"first_name": " Ana ", "last_name": "", "language": "es"},
    )

    body = response.json()
    assert (body["first_name"], body["last_name"], body["language"]) == ("Ana", "", "es")


@pytest.mark.parametrize("payload", [{"role": None}, {"is_active": None}])
async def test_update_rejects_null(client, make_user, as_admin, payload):
    user = await make_user("ana@example.com")

    response = await client.patch(f"/api/users/{user.id}", headers=as_admin, json=payload)

    assert response.json()["error"]["code"] == "invalid_request"


async def test_update_rejects_unknown_fields(client, make_user, as_admin):
    user = await make_user("ana@example.com")

    response = await client.patch(
        f"/api/users/{user.id}", headers=as_admin, json={"email": "x@example.com"}
    )

    assert response.status_code == 422


async def test_deactivating_ends_the_users_sessions(client, db, make_user, as_admin):
    user = await make_user("ana@example.com")
    await sessions.issue(db, user)

    await client.patch(f"/api/users/{user.id}", headers=as_admin, json={"is_active": False})

    assert await _live_sessions(db, user.id) == 0


async def test_demoting_ends_the_users_sessions_but_promoting_does_not(
    client, db, make_user, as_admin
):
    demoted = await make_user("demoted@example.com", role=Role.user)
    promoted = await make_user("promoted@example.com", role=Role.none)
    demoted_id, promoted_id = demoted.id, promoted.id
    await sessions.issue(db, demoted)
    await sessions.issue(db, promoted)

    await client.patch(f"/api/users/{demoted_id}", headers=as_admin, json={"role": "none"})
    await client.patch(f"/api/users/{promoted_id}", headers=as_admin, json={"role": "user"})

    assert await _live_sessions(db, demoted_id) == 0
    assert await _live_sessions(db, promoted_id) == 1


async def test_switching_to_password_needs_a_password_first(client, make_user, as_admin):
    user = await make_user("ana@example.com", auth_method=AuthMethod.otp, password=None)

    response = await client.patch(
        f"/api/users/{user.id}", headers=as_admin, json={"auth_method": "password"}
    )

    assert response.json()["error"]["code"] == "password_required"


async def test_switching_to_otp_drops_the_password(client, db, make_user, as_admin):
    user_id = (await make_user("ana@example.com")).id

    await client.patch(f"/api/users/{user_id}", headers=as_admin, json={"auth_method": "otp"})

    db.expire_all()
    stored = await db.get(User, user_id)
    assert stored.auth_method is AuthMethod.otp
    assert stored.password_hash is None


# ---- last admin ----


@pytest.mark.parametrize("payload", [{"role": "user"}, {"is_active": False}])
async def test_the_last_active_admin_cannot_lose_admin_rights(client, admin, as_admin, payload):
    response = await client.patch(f"/api/users/{admin.id}", headers=as_admin, json=payload)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "last_admin"


async def test_an_inactive_admin_does_not_count(client, make_user, admin, as_admin):
    await make_user("off@example.com", role=Role.admin, is_active=False)

    response = await client.patch(f"/api/users/{admin.id}", headers=as_admin, json={"role": "user"})

    assert response.json()["error"]["code"] == "last_admin"


async def test_an_admin_can_step_down_when_another_remains(client, make_user, admin, as_admin):
    await make_user("other@example.com", role=Role.admin)

    response = await client.patch(f"/api/users/{admin.id}", headers=as_admin, json={"role": "user"})

    assert response.json()["role"] == "user"


async def test_two_admins_demoting_each_other_at_once_leave_one_admin(client, db, make_user, admin):
    other = await make_user("other@example.com", role=Role.admin)
    a, b = (
        auth(create_access_token(admin.id, "admin")),
        auth(create_access_token(other.id, "admin")),
    )

    results = await asyncio.gather(
        client.patch(f"/api/users/{other.id}", headers=a, json={"role": "user"}),
        client.patch(f"/api/users/{admin.id}", headers=b, json={"role": "user"}),
    )

    assert sorted(r.status_code for r in results) in ([200, 403], [200, 409])
    db.expire_all()
    admins = await db.scalars(select(User).where(User.role == Role.admin, User.is_active))
    assert len(admins.all()) == 1


# ---- set password ----


async def test_set_password_switches_method_and_ends_sessions(client, db, make_user, as_admin):
    user = await make_user("ana@example.com", auth_method=AuthMethod.otp, password=None)
    user_id = user.id
    await sessions.issue(db, user)

    response = await client.post(
        f"/api/users/{user_id}/set-password", headers=as_admin, json={"password": "a brand new one"}
    )

    assert response.json()["auth_method"] == "password"
    db.expire_all()
    assert verify_password("a brand new one", (await db.get(User, user_id)).password_hash)
    assert await _live_sessions(db, user_id) == 0


async def test_set_password_applies_the_rules(client, make_user, as_admin):
    user = await make_user("ana@example.com")

    response = await client.post(
        f"/api/users/{user.id}/set-password", headers=as_admin, json={"password": "1234567890"}
    )

    assert response.json()["error"]["code"] == "weak_password"


# ---- delete ----


async def test_delete_removes_the_user_and_their_sessions(client, db, make_user, as_admin):
    user = await make_user("ana@example.com")
    await sessions.issue(db, user)
    user_id = user.id

    response = await client.delete(f"/api/users/{user_id}", headers=as_admin)

    assert response.status_code == 204
    db.expire_all()
    assert await db.get(User, user_id) is None
    assert await _live_sessions(db, user_id) == 0


async def test_an_admin_cannot_delete_themself(client, make_user, admin, as_admin):
    await make_user("other@example.com", role=Role.admin)

    response = await client.delete(f"/api/users/{admin.id}", headers=as_admin)

    assert response.json()["error"]["code"] == "cannot_delete_self"


async def test_two_admins_deleting_each_other_at_once_leave_one_admin(client, db, make_user, admin):
    other = await make_user("other@example.com", role=Role.admin)
    a, b = (
        auth(create_access_token(admin.id, "admin")),
        auth(create_access_token(other.id, "admin")),
    )

    results = await asyncio.gather(
        client.delete(f"/api/users/{other.id}", headers=a),
        client.delete(f"/api/users/{admin.id}", headers=b),
    )

    statuses = sorted(r.status_code for r in results)
    assert statuses[0] == 204
    assert statuses[1] in (401, 403)  # the loser was deleted: refused before or under the lock
    db.expire_all()
    admins = await db.scalars(select(User).where(User.role == Role.admin, User.is_active))
    assert len(admins.all()) == 1


async def test_an_admin_can_delete_another_admin(client, db, make_user, as_admin):
    target_id = (await make_user("target@example.com", role=Role.admin)).id

    response = await client.delete(f"/api/users/{target_id}", headers=as_admin)

    assert response.status_code == 204


async def test_delete_unknown_user_is_404(client, as_admin):
    response = await client.delete("/api/users/999999", headers=as_admin)

    assert response.status_code == 404


async def test_an_admin_demoted_while_waiting_for_the_lock_is_refused(client, db, make_user, admin):
    acting = await make_user("acting@example.com", role=Role.admin)
    target = await make_user("target@example.com")
    acting_id, target_id = acting.id, target.id
    async with get_sessionmaker()() as holder:
        await holder.execute(
            select(User).where(User.role == Role.admin, User.is_active).with_for_update()
        )
        request = asyncio.create_task(
            client.delete(
                f"/api/users/{target_id}", headers=auth(create_access_token(acting_id, "admin"))
            )
        )
        await asyncio.sleep(0.2)  # the delete passed the role check and waits for the lock
        await holder.execute(update(User).where(User.id == acting_id).values(role=Role.user))
        await holder.commit()

    response = await request

    assert response.status_code == 403
    db.expire_all()
    assert await db.get(User, target_id) is not None


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("patch", "/api/users/{id}", {"first_name": "Renamed"}),
        ("patch", "/api/users/{id}", {"role": "none"}),
        ("patch", "/api/users/{id}", {"is_active": False}),
        ("post", "/api/users/{id}/set-password", {"password": "a brand new one"}),
        ("delete", "/api/users/{id}", None),
    ],
)
async def test_a_user_deleted_while_the_request_waits_answers_404(
    client, db, make_user, as_admin, method, path, body
):
    target_id = (await make_user("target@example.com")).id
    async with get_sessionmaker()() as holder:
        await holder.execute(select(User).where(User.id == target_id).with_for_update())
        request = asyncio.create_task(
            client.request(method, path.format(id=target_id), headers=as_admin, json=body)
        )
        await asyncio.sleep(0.2)  # the request now waits for the target's row lock
        await holder.execute(delete(User).where(User.id == target_id))
        await holder.commit()

    response = await request

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"
    db.expire_all()
    assert await db.get(User, target_id) is None


async def test_two_admins_deleting_the_same_user_get_204_and_404(client, make_user, admin):
    other = await make_user("other@example.com", role=Role.admin)
    target_id = (await make_user("target@example.com")).id
    a, b = (
        auth(create_access_token(admin.id, "admin")),
        auth(create_access_token(other.id, "admin")),
    )

    results = await asyncio.gather(
        client.delete(f"/api/users/{target_id}", headers=a),
        client.delete(f"/api/users/{target_id}", headers=b),
    )

    assert sorted(r.status_code for r in results) == [204, 404]


@pytest.mark.parametrize(
    "name",
    [
        "A\u0001b",
        "line\nbreak",
        "tab\there",
        "evil\u202eexe.txt",
        "x\u2066y",
        "zero\u200bwidth",
        "bom\ufeff",
    ],
)
async def test_names_with_control_or_direction_characters_are_rejected(
    client, make_user, as_admin, name
):
    user = await make_user("ana@example.com")

    created = await client.post(
        "/api/users", headers=as_admin, json={"email": "n@example.com", "first_name": name}
    )
    updated = await client.patch(
        f"/api/users/{user.id}", headers=as_admin, json={"last_name": name}
    )

    assert (created.status_code, updated.status_code) == (422, 422)


async def test_names_keep_accents_and_other_scripts(client, make_user, as_admin):
    user = await make_user("ana@example.com")

    response = await client.patch(
        f"/api/users/{user.id}",
        headers=as_admin,
        json={"first_name": "Uxía", "last_name": "Núñez 李"},
    )

    assert (response.json()["first_name"], response.json()["last_name"]) == ("Uxía", "Núñez 李")
