from fastapi import APIRouter

from app.api.dependencies import ProductServiceDep
from app.schemas.products import ProductOut

router = APIRouter()


@router.get("/products", response_model=list[ProductOut], tags=["Справочники"])
async def products(service: ProductServiceDep):
    return await service.products()
