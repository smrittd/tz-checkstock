from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.uow import UnitOfWork
from app.services.health import HealthService
from app.services.history import HistoryService
from app.services.inventory import InventoryService
from app.services.movements import MovementService
from app.services.products import ProductService
from app.services.warehouses import WarehouseService


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    # Each HTTP request owns a separate session; concurrent tasks never share one.
    async with request.app.state.session_factory() as session:
        yield session


async def get_uow(session: Annotated[AsyncSession, Depends(get_session)]) -> UnitOfWork:
    return UnitOfWork(session)


async def get_products_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> ProductService:
    return ProductService(uow)


ProductServiceDep = Annotated[ProductService, Depends(get_products_service)]


async def get_warehouses_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> WarehouseService:
    return WarehouseService(uow)


WarehouseServiceDep = Annotated[WarehouseService, Depends(get_warehouses_service)]


async def get_inventory_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> InventoryService:
    return InventoryService(uow)


InventoryServiceDep = Annotated[InventoryService, Depends(get_inventory_service)]


async def get_movements_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> MovementService:
    return MovementService(uow)


MovementServiceDep = Annotated[MovementService, Depends(get_movements_service)]


async def get_history_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> HistoryService:
    return HistoryService(uow)


HistoryServiceDep = Annotated[HistoryService, Depends(get_history_service)]


async def get_health_service(uow: Annotated[UnitOfWork, Depends(get_uow)]) -> HealthService:
    return HealthService(uow)


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]

Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
