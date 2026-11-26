import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.users.models import Role, User


@pytest.mark.parametrize(
    ("role", "minimum", "expected"),
    [
        (Role.none, Role.user, False),
        (Role.user, Role.user, True),
        (Role.user, Role.admin, False),
        (Role.admin, Role.user, True),
        (Role.admin, Role.admin, True),
    ],
)
def test_has_role_compares_levels(role, minimum, expected):
    assert User(role=role).has_role(minimum) is expected


async def test_new_user_defaults_have_no_permissions(db):
    user = User(email="new@example.com")
    db.add(user)
    await db.commit()

    assert user.role is Role.none
    assert user.is_active is False
    assert user.created_at is not None


def test_email_is_normalised_when_assigned():
    assert User(email="  Mixed.Case@Example.COM ").email == "mixed.case@example.com"


async def test_emails_differing_only_in_case_cannot_both_exist(db, make_user):
    await make_user("dup@example.com")
    db.add(User(email="Dup@Example.com"))

    with pytest.raises(IntegrityError):
        await db.commit()


async def test_database_enforces_case_insensitive_unique_emails_for_raw_writes(db, make_user):
    await make_user("dup@example.com")

    with pytest.raises(IntegrityError):
        await db.execute(
            text(
                "INSERT INTO users (email, first_name, last_name, auth_method, role, is_active,"
                " language, theme) VALUES ('DUP@example.com', '', '', 'otp', 'none', false,"
                " 'en', 'system')"
            )
        )


async def test_database_rejects_a_mixed_case_email_written_without_the_model(db, make_user):
    user = await make_user("ana@example.com")

    with pytest.raises(IntegrityError):
        await db.execute(
            text("UPDATE users SET email = 'Ana@example.com' WHERE id = :id"), {"id": user.id}
        )


async def test_database_rejects_an_unknown_role(db, make_user):
    user = await make_user()

    with pytest.raises(IntegrityError):
        await db.execute(text("UPDATE users SET role = 'owner' WHERE id = :id"), {"id": user.id})
