from uuid import UUID

from app.db.uow import UnitOfWork


class HistoryService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def history(
        self, product_id: int | None, movement_id: UUID | None, limit: int, offset: int
    ) -> dict:
        items, total = await self.uow.events.history(product_id, movement_id, limit, offset)
        return {"items": items, "total": total, "limit": limit, "offset": offset}
