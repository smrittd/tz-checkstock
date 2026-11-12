from uuid import UUID

from sqlalchemy import func, select

from app.models.event import Event
from app.repositories.base import BaseRepository


class EventsRepository(BaseRepository):
    async def has_event(self, movement_id: UUID, action: str) -> bool:
        return (
            await self._session.scalar(
                select(Event.id).where(Event.movement_id == movement_id, Event.action == action)
            )
        ) is not None

    async def history(
        self, product_id: int | None, movement_id: UUID | None, limit: int, offset: int
    ) -> tuple[list[Event], int]:
        query = select(Event)
        if product_id is not None:
            query = query.where(Event.product_id == product_id)
        if movement_id is not None:
            query = query.where(Event.movement_id == movement_id)
        total = await self._session.scalar(select(func.count()).select_from(query.subquery()))
        items = await self._session.scalars(
            query.order_by(Event.id.desc()).limit(limit).offset(offset)
        )
        return list(items), total
