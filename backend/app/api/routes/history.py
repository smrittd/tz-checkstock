from uuid import UUID

from fastapi import APIRouter

from app.api.dependencies import HistoryServiceDep, Limit, Offset
from app.schemas.common import Page
from app.schemas.history import EventOut

router = APIRouter()


@router.get("/history", response_model=Page[EventOut], tags=["История"])
async def history(
    service: HistoryServiceDep,
    product_id: int | None = None,
    movement_id: UUID | None = None,
    limit: Limit = 50,
    offset: Offset = 0,
):
    return await service.history(product_id, movement_id, limit, offset)
