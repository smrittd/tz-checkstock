from fastapi import APIRouter

from app.api.routes import history, inventory, movements, products, warehouses

router = APIRouter(prefix="/api/v1")
router.include_router(products.router)
router.include_router(warehouses.router)
router.include_router(inventory.router)
router.include_router(movements.router)
router.include_router(history.router)
