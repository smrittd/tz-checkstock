from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base


class BaseRepository:
    def __init__(self, session: AsyncSession):
        self._session = session

    def add(self, entity: Base) -> None:
        self._session.add(entity)

    async def flush(self) -> None:
        await self._session.flush()
