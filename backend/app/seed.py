import asyncio

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import settings
from app.db.session import create_database_engine
from app.db.uow import UnitOfWork
from app.services.demo import DemoService


async def seed_demo(session: AsyncSession) -> bool:
    return await DemoService(UnitOfWork(session)).seed_demo()


async def main() -> None:
    engine = create_database_engine(settings.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with factory() as session:
            loaded = await seed_demo(session)
            print("Демо-данные добавлены." if loaded else "Демо-данные уже загружены.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
