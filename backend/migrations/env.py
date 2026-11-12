import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection, pool
from sqlalchemy.ext.asyncio import create_async_engine

from app import models  # noqa: F401 -- register all tables in Base.metadata
from app.core.config import settings
from app.db.base import Base

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_online() -> None:
    engine = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
        connect_args={"timeout": 5},
    )
    try:
        async with engine.connect() as connection:
            # Alembic's revision API is synchronous; run_sync adapts I/O to the async driver.
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=settings.database_url,
        target_metadata=Base.metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif connection := config.attributes.get("connection"):
    # Tests supply a connection from their existing event loop.
    run_migrations(connection)
else:
    asyncio.run(run_online())
