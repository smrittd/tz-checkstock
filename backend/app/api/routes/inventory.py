from fastapi import APIRouter

from app.api.dependencies import InventoryServiceDep
from app.schemas.inventory import InventoryOut

router = APIRouter()


@router.get("/inventory", response_model=InventoryOut, tags=["Остатки"])
async def inventory(service: InventoryServiceDep):
    return await service.inventory()
