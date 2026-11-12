from pydantic import BaseModel

from app.schemas.products import ProductOut
from app.schemas.warehouses import WarehouseOut


class Totals(BaseModel):
    on_hand: int = 0
    reserved: int = 0
    available: int = 0
    transfer_in_transit: int = 0
    fbs_in_transit: int = 0
    fbo_in_transit: int = 0
    at_marketplace: int = 0
    delivered: int = 0
    total_received: int = 0


class WarehouseStock(BaseModel):
    warehouse_id: int
    on_hand: int
    reserved: int
    available: int


class ExternalStock(BaseModel):
    destination: str
    quantity: int


class ProductStock(ProductOut):
    warehouses: list[WarehouseStock]
    totals: Totals
    marketplaces: list[ExternalStock]


class InventoryOut(BaseModel):
    store: str
    warehouses: list[WarehouseOut]
    products: list[ProductStock]
    totals: Totals
