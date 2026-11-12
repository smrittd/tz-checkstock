from uuid import UUID

from fastapi import APIRouter

from app.api.dependencies import Limit, MovementServiceDep, Offset
from app.schemas.common import Page
from app.schemas.movements import (
    Action,
    Kind,
    MovementOut,
    ReceiptInput,
    ShipmentInput,
    Status,
    TransferInput,
)

router = APIRouter()


@router.post("/receipts", response_model=MovementOut, status_code=201, tags=["Движения"])
async def receipt(data: ReceiptInput, service: MovementServiceDep):
    return await service.receipt(data)


@router.post("/transfers", response_model=MovementOut, status_code=201, tags=["Движения"])
async def transfer(data: TransferInput, service: MovementServiceDep):
    return await service.transfer(data)


@router.post("/fbs", response_model=MovementOut, status_code=201, tags=["Движения"])
async def fbs(data: ShipmentInput, service: MovementServiceDep):
    return await service.fbs(data)


@router.post("/fbo", response_model=MovementOut, status_code=201, tags=["Движения"])
async def fbo(data: ShipmentInput, service: MovementServiceDep):
    return await service.fbo(data)


@router.get("/movements", response_model=Page[MovementOut], tags=["Движения"])
async def movements(
    service: MovementServiceDep,
    kind: Kind | None = None,
    status: Status | None = None,
    product_id: int | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return await service.movements(kind, status, product_id, limit, offset)


@router.get("/movements/{movement_id}", response_model=MovementOut, tags=["Движения"])
async def movement(movement_id: UUID, service: MovementServiceDep):
    return await service.movement(movement_id)


@router.post("/movements/{movement_id}/{action}", response_model=MovementOut, tags=["Движения"])
async def confirm(movement_id: UUID, action: Action, service: MovementServiceDep):
    return await service.confirm(movement_id, action)
