"""User management rules shared by the admin endpoints."""

from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import sessions
from app.core.errors import AppError
from app.core.security import hash_password_async, validate_password
from app.users.models import ROLE_LEVEL, AuthMethod, Role, User, normalise_email
from app.users.schemas import UserCreate, UserUpdate

LAST_ADMIN = AppError(409, "last_admin", "At least one active administrator must remain")
USER_NOT_FOUND = AppError(404, "user_not_found", "User not found")


async def list_users(
    db: AsyncSession,
    *,
    q: str | None,
    role: Role | None,
    active: bool | None,
    page: int,
    size: int,
) -> tuple[list[User], int]:
    query = select(User)
    if q and q.strip():
        # autoescape: % and _ typed by the admin are literal characters, not wildcards
        term = q.strip()
        full_name = func.concat(User.first_name, " ", User.last_name)
        query = query.where(
            or_(
                User.email.icontains(term, autoescape=True),
                full_name.icontains(term, autoescape=True),
            )
        )
    if role is not None:
        query = query.where(User.role == role)
    if active is not None:
        query = query.where(User.is_active.is_(active))
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.scalars(query.order_by(User.email).offset((page - 1) * size).limit(size))
    return list(rows), total or 0


async def get_user(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise USER_NOT_FOUND
    return user


async def _set_password(user: User, password: str) -> None:
    validate_password(password, user.email)
    user.password_hash = await hash_password_async(password)
    user.auth_method = AuthMethod.password


async def create_user(db: AsyncSession, body: UserCreate) -> User:
    email = normalise_email(body.email)
    if await db.scalar(select(User.id).where(User.email == email)):
        raise AppError(409, "email_taken", "A user with this email already exists")
    user = User(
        email=email,
        first_name=body.first_name,
        last_name=body.last_name,
        role=body.role,
        auth_method=AuthMethod.otp,
        language=body.language,
        is_active=True,
        # The admin vouches for the address: never treated as an unconfirmed sign-up.
        email_verified_at=datetime.now(UTC),
    )
    if body.auth_method is AuthMethod.password:
        if not body.password:
            raise AppError(400, "password_required", "A password is required for this method")
        await _set_password(user, body.password)
    elif body.password is not None:
        raise AppError(400, "password_not_allowed", "Code-login users have no password")
    db.add(user)
    try:
        await db.commit()
    except IntegrityError as exc:  # created concurrently with the same email
        await db.rollback()
        raise AppError(409, "email_taken", "A user with this email already exists") from exc
    return user


async def _lock_admins(db: AsyncSession, acting: User) -> set[int]:
    """Lock the active admins' rows until commit and check the acting admin is still one of them.
    Changes that touch admins are thus applied one at a time: two admins demoting or deleting each
    other at the same moment cannot leave none."""
    admins = set(
        await db.scalars(
            select(User.id)
            .where(User.role == Role.admin, User.is_active.is_(True))
            .order_by(User.id)
            .with_for_update()
        )
    )
    if acting.id not in admins:
        await db.rollback()
        raise AppError(403, "forbidden", "You do not have permission for this action")
    return admins


async def _lock_user(db: AsyncSession, user_id: int) -> User:
    """Lock the target user's row until commit and read it fresh; 404 when it no longer exists
    (deleted by a concurrent request). Always taken after `_lock_admins`, never before, so every
    transaction locks rows in the same order."""
    user = await db.scalar(
        select(User)
        .where(User.id == user_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None:
        await db.rollback()
        raise USER_NOT_FOUND
    return user


async def update_user(db: AsyncSession, user_id: int, body: UserUpdate, acting: User) -> User:
    changes = body.model_dump(exclude_unset=True)
    if any(value is None for value in changes.values()):
        raise AppError(400, "invalid_request", "Fields cannot be null")
    admin_change = "role" in changes or "is_active" in changes
    admins = await _lock_admins(db, acting) if admin_change else set()
    user = await _lock_user(db, user_id)
    if admin_change:
        loses_admin = changes.get("role", Role.admin) is not Role.admin or (
            changes.get("is_active") is False
        )
        # The acting admin is in `admins`, so this only happens when they demote themselves.
        if loses_admin and admins == {user.id}:
            await db.rollback()
            raise LAST_ADMIN
    if changes.get("auth_method") is AuthMethod.password and user.password_hash is None:
        await db.rollback()
        raise AppError(400, "password_required", "Set a password first (set-password)")
    if changes.get("auth_method") is AuthMethod.otp:
        user.password_hash = None
    ends_sessions = changes.get("is_active") is False or (
        "role" in changes and ROLE_LEVEL[changes["role"]] < ROLE_LEVEL[user.role]
    )
    for field, value in changes.items():
        setattr(user, field, value)
    if ends_sessions:  # in the same transaction: a refresh waiting on the row then sees it
        await sessions.revoke_all(db, user.id, commit=False)
    await db.commit()
    return user


async def set_password(db: AsyncSession, user_id: int, password: str) -> User:
    user = await _lock_user(db, user_id)
    try:
        await _set_password(user, password)
    except AppError:
        await db.rollback()
        raise
    await sessions.revoke_all(db, user.id, commit=False)
    await db.commit()
    return user


async def delete_user(db: AsyncSession, user_id: int, acting_admin: User) -> None:
    if user_id == acting_admin.id:
        raise AppError(409, "cannot_delete_self", "You cannot delete your own account")
    # The acting admin, still an active admin under the lock, remains: never the last one.
    await _lock_admins(db, acting_admin)
    user = await _lock_user(db, user_id)
    await db.delete(user)  # sessions, codes and failed logins go with it (ON DELETE CASCADE)
    await db.commit()
