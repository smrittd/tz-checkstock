from fastapi import APIRouter

from app.api.dependencies import WarehouseServiceDep
from app.schemas.warehouses import WarehouseInput, WarehouseOut

router = APIRouter()


@router.get("/warehouses", response_model=list[WarehouseOut], tags=["Склады"])
async def warehouses(service: WarehouseServiceDep, include_archived: bool = True):
    return await service.warehouses(include_archived)


@router.post("/warehouses", response_model=WarehouseOut, status_code=201, tags=["Склады"])
async def create_warehouse(data: WarehouseInput, service: WarehouseServiceDep):
    return await service.create_warehouse(data)


@router.patch("/warehouses/{warehouse_id}", response_model=WarehouseOut, tags=["Склады"])
async def rename_warehouse(warehouse_id: int, data: WarehouseInput, service: WarehouseServiceDep):
    return await service.rename_warehouse(warehouse_id, data)


@router.delete("/warehouses/{warehouse_id}", response_model=WarehouseOut, tags=["Склады"])
async def archive_warehouse(warehouse_id: int, service: WarehouseServiceDep):
    return await service.archive_warehouse(warehouse_id)
