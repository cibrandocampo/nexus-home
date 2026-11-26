import pytest

from app.auth.deps import CurrentUser, RequireAdmin, RequireUser
from app.core.security import create_access_token
from app.users.models import Role


@pytest.fixture
def guarded(app):
    @app.get("/api/t/me")
    async def me(user: CurrentUser):
        return {"id": user.id}

    @app.get("/api/t/user")
    async def user_only(user: RequireUser):
        return {"ok": True}

    @app.get("/api/t/admin")
    async def admin_only(user: RequireAdmin):
        return {"ok": True}

    return app


def _auth(user) -> dict:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role.value)}"}


async def test_current_user_requires_a_bearer_token(guarded, client):
    response = await client.get("/api/t/me")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_current_user_resolves_the_token_owner(guarded, client, make_user):
    user = await make_user()

    response = await client.get("/api/t/me", headers=_auth(user))

    assert response.json() == {"id": user.id}


async def test_inactive_user_is_rejected(guarded, client, make_user):
    user = await make_user(is_active=False)

    response = await client.get("/api/t/me", headers=_auth(user))

    assert response.status_code == 401


async def test_token_of_a_deleted_user_is_rejected(guarded, client, make_user, db):
    user = await make_user()
    headers = _auth(user)
    await db.delete(user)
    await db.commit()

    response = await client.get("/api/t/me", headers=headers)

    assert response.status_code == 401


@pytest.mark.parametrize(
    ("role", "path", "status"),
    [
        (Role.none, "/api/t/me", 200),
        (Role.none, "/api/t/user", 403),
        (Role.none, "/api/t/admin", 403),
        (Role.user, "/api/t/user", 200),
        (Role.user, "/api/t/admin", 403),
        (Role.admin, "/api/t/user", 200),
        (Role.admin, "/api/t/admin", 200),
    ],
)
async def test_role_guards(guarded, client, make_user, role, path, status):
    user = await make_user(role=role)

    response = await client.get(path, headers=_auth(user))

    assert response.status_code == status
    if status == 403:
        assert response.json()["error"]["code"] == "forbidden"
