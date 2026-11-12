from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.balances import BalancesRepository
from app.repositories.events import EventsRepository
from app.repositories.movements import MovementsRepository
from app.repositories.products import ProductsRepository
from app.repositories.system import SystemRepository
from app.repositories.warehouses import WarehousesRepository


class UnitOfWork:
    """Одна сессия и одна транзакция для всех изменений бизнес-операции."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self.products = ProductsRepository(session)
        self.warehouses = WarehousesRepository(session)
        self.balances = BalancesRepository(session)
        self.movements = MovementsRepository(session)
        self.events = EventsRepository(session)
        self.system = SystemRepository(session)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        # SQLAlchemy commits on success and rolls back on errors, including cancellation.
        async with self._session.begin():
            await self.system.lock_store()
            yield

    async def begin_snapshot(self) -> None:
        """Уровень изоляции задаётся до первого чтения в транзакции."""
        await self._session.execute(
            text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        )
