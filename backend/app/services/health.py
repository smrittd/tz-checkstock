from app.db.uow import UnitOfWork


class HealthService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def ready(self) -> None:
        await self.uow.system.store()
