from sqlalchemy import select

from app.models.seed_run import SeedRun
from app.models.store import Store
from app.repositories.base import BaseRepository


class SystemRepository(BaseRepository):
    async def store(self) -> Store:
        return (await self._session.execute(select(Store).where(Store.id == 1))).scalar_one()

    async def lock_store(self) -> None:
        # All writers acquire this lock, including writes to initially absent balance rows.
        (
            await self._session.execute(select(Store).where(Store.id == 1).with_for_update())
        ).scalar_one()

    async def seed_run(self, name: str) -> SeedRun | None:
        return await self._session.get(SeedRun, name)
