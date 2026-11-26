"""Request dependencies: the logged-in user and role checks."""

from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.users.models import Role, User

_bearer = HTTPBearer(auto_error=False)


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    if credentials is None:
        raise AppError(401, "unauthorized", "Authentication required")
    user = await db.get(User, decode_access_token(credentials.credentials))
    if user is None or not user.is_active:
        raise AppError(401, "unauthorized", "Authentication required")
    return user


def require_role(minimum: Role):
    """Dependency factory: the user must have at least `minimum` (admin passes every check)."""

    async def check(user: Annotated[User, Depends(current_user)]) -> User:
        if not user.has_role(minimum):
            raise AppError(403, "forbidden", "You do not have permission for this action")
        return user

    return check


CurrentUser = Annotated[User, Depends(current_user)]
RequireUser = Annotated[User, Depends(require_role(Role.user))]
RequireAdmin = Annotated[User, Depends(require_role(Role.admin))]
