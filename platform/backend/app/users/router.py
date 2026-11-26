"""/api/users: account management for administrators."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import RequireAdmin
from app.core.db import get_session
from app.core.types import NO_NUL, IdPath
from app.users import service
from app.users.models import Role
from app.users.schemas import SetPassword, UserCreate, UserOut, UserPage, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])

Db = Annotated[AsyncSession, Depends(get_session)]


@router.get("")
async def list_users(
    admin: RequireAdmin,
    db: Db,
    q: Annotated[str | None, Query(max_length=100, pattern=NO_NUL)] = None,
    role: Role | None = None,
    active: bool | None = None,
    page: Annotated[int, Query(ge=1, le=100_000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> UserPage:
    users, total = await service.list_users(db, q=q, role=role, active=active, page=page, size=size)
    return UserPage(
        items=[UserOut.model_validate(u) for u in users], total=total, page=page, size=size
    )


@router.post("", status_code=201)
async def create_user(body: UserCreate, admin: RequireAdmin, db: Db) -> UserOut:
    return UserOut.model_validate(await service.create_user(db, body))


@router.get("/{user_id}")
async def get_user(user_id: IdPath, admin: RequireAdmin, db: Db) -> UserOut:
    return UserOut.model_validate(await service.get_user(db, user_id))


@router.patch("/{user_id}")
async def update_user(user_id: IdPath, body: UserUpdate, admin: RequireAdmin, db: Db) -> UserOut:
    return UserOut.model_validate(await service.update_user(db, user_id, body, admin))


@router.post("/{user_id}/set-password")
async def set_password(user_id: IdPath, body: SetPassword, admin: RequireAdmin, db: Db) -> UserOut:
    return UserOut.model_validate(await service.set_password(db, user_id, body.password))


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: IdPath, admin: RequireAdmin, db: Db) -> None:
    await service.delete_user(db, user_id, admin)
