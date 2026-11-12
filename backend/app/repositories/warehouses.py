from sqlalchemy import select

from app.models.warehouse import Warehouse
from app.repositories.base import BaseRepository


class WarehousesRepository(BaseRepository):
    async def warehouse(self, warehouse_id: int) -> Warehouse | None:
        return await self._session.get(Warehouse, warehouse_id)

    async def warehouse_by_name(self, name_key: str) -> Warehouse | None:
        return await self._session.scalar(select(Warehouse).where(Warehouse.name_key == name_key))

    async def warehouses(self, include_archived: bool = True) -> list[Warehouse]:
        query = select(Warehouse).order_by(Warehouse.id)
        if not include_archived:
            query = query.where(Warehouse.archived_at.is_(None))
        return list(await self._session.scalars(query))
