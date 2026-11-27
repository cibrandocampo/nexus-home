"""Reading the event history (collected by devices/history.py)."""

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.devices.models import Device, DeviceEvent
from app.devices.schemas import EventOut, Ref
from app.users.models import User


def _user_name(user: User) -> str | None:
    # Only the name: users see each other's names in the history, never their email addresses.
    return f"{user.first_name} {user.last_name}".strip() or None


async def list_events(
    db: AsyncSession,
    *,
    device_pk: int | None,
    events: list[str] | None,
    since: datetime | None,
    until: datetime | None,
    page: int,
    size: int,
) -> tuple[list[EventOut], int]:
    query = (
        select(DeviceEvent, Device.name, User)
        .join(Device, Device.id == DeviceEvent.device_pk)
        .outerjoin(User, User.id == DeviceEvent.user_id)
    )
    if device_pk is not None:
        query = query.where(DeviceEvent.device_pk == device_pk)
    if events:
        query = query.where(DeviceEvent.event.in_(events))
    if since is not None:
        query = query.where(DeviceEvent.at >= since)
    if until is not None:
        query = query.where(DeviceEvent.at < until)
    total = await db.scalar(select(func.count()).select_from(query.subquery()))
    rows = await db.execute(
        query.order_by(DeviceEvent.at.desc(), DeviceEvent.id.desc())
        .offset((page - 1) * size)
        .limit(size)
    )
    items = [
        EventOut(
            id=e.id,
            at=e.at,
            event=e.event,
            source=e.source,
            reason=e.reason,
            value=e.value,
            device=Ref(id=e.device_pk, name=device_name),
            user=Ref(id=user.id, name=_user_name(user)) if user else None,
        )
        for e, device_name, user in rows
    ]
    return items, total or 0
