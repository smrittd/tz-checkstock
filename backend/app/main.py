from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.exception_handlers import database_error, domain_error, validation_error
from app.api.router import router
from app.api.routes.health import router as health_router
from app.core.config import settings
from app.core.errors import DomainError
from app.db.session import create_database_engine
from app.schemas.common import ErrorOut


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    engine = create_database_engine(app.state.database_url)
    app.state.session_factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield
    finally:
        await engine.dispose()


def create_app(database_url: str | None = None) -> FastAPI:
    instance = FastAPI(
        title="CheckStock API",
        version="0.1.0",
        lifespan=lifespan,
        description="Учёт товаров одного магазина на складах фулфилмента.",
        responses={
            404: {"model": ErrorOut},
            409: {"model": ErrorOut},
            422: {"model": ErrorOut},
            503: {"model": ErrorOut},
        },
    )
    instance.state.database_url = database_url or settings.database_url
    instance.add_exception_handler(DomainError, domain_error)
    instance.add_exception_handler(RequestValidationError, validation_error)
    instance.add_exception_handler(OperationalError, database_error)
    instance.add_exception_handler(TimeoutError, database_error)
    instance.add_exception_handler(OSError, database_error)
    instance.include_router(router)
    instance.include_router(health_router)
    return instance


app = create_app()
