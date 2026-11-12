from sqlalchemy import select

from app.models.balance import Balance
from app.models.warehouse import Warehouse
from app.repositories.base import BaseRepository


class BalancesRepository(BaseRepository):
    async def balance(self, product_id: int, warehouse_id: int) -> Balance | None:
        return await self._session.get(Balance, (product_id, warehouse_id))

    async def balances(self) -> list[Balance]:
        return list(await self._session.scalars(select(Balance)))

    async def alternative_balances(self, product_id: int, warehouse_id: int):
        return (
            await self._session.execute(
                select(Balance, Warehouse)
                .join(Warehouse, Warehouse.id == Balance.warehouse_id)
                .where(Balance.product_id == product_id, Balance.warehouse_id != warehouse_id)
                .order_by(Warehouse.id)
            )
        ).all()
