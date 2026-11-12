from app.db.uow import UnitOfWork
from app.schemas.inventory import ExternalStock, InventoryOut, ProductStock, Totals, WarehouseStock
from app.schemas.warehouses import WarehouseOut


class InventoryService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def inventory(self) -> InventoryOut:
        # Use one committed snapshot across all inventory queries.
        await self.uow.begin_snapshot()
        warehouses = await self.uow.warehouses.warehouses()
        products = await self.uow.products.products()
        balances = {
            (item.product_id, item.warehouse_id): item
            for item in await self.uow.balances.balances()
        }
        quantities = await self.uow.movements.movement_quantities()
        market_rows = await self.uow.movements.marketplace_quantities()
        totals = Totals()
        items = []
        quantity_fields = {
            ("receipt", "received"): "total_received",
            ("transfer", "in_transit"): "transfer_in_transit",
            ("fbs", "in_transit"): "fbs_in_transit",
            ("fbo", "in_transit"): "fbo_in_transit",
            ("fbo", "received"): "at_marketplace",
            ("fbs", "delivered"): "delivered",
        }
        for product in products:
            stocks = []
            product_totals = Totals()
            for warehouse in warehouses:
                balance = balances.get((product.id, warehouse.id))
                on_hand, reserved = (balance.on_hand, balance.reserved) if balance else (0, 0)
                stocks.append(
                    WarehouseStock(
                        warehouse_id=warehouse.id,
                        on_hand=on_hand,
                        reserved=reserved,
                        available=on_hand - reserved,
                    )
                )
                product_totals.on_hand += on_hand
                product_totals.reserved += reserved
                product_totals.available += on_hand - reserved
            for product_id, kind, status, quantity in quantities:
                field = quantity_fields.get((kind, status))
                if product_id == product.id and field:
                    setattr(product_totals, field, quantity)
            for field in Totals.model_fields:
                setattr(totals, field, getattr(totals, field) + getattr(product_totals, field))
            items.append(
                ProductStock(
                    id=product.id,
                    sku=product.sku,
                    name=product.name,
                    warehouses=stocks,
                    totals=product_totals,
                    marketplaces=[
                        ExternalStock(destination=name, quantity=qty)
                        for pid, name, qty in market_rows
                        if pid == product.id
                    ],
                )
            )
        return InventoryOut(
            store=(await self.uow.system.store()).name,
            warehouses=[WarehouseOut.model_validate(item) for item in warehouses],
            products=items,
            totals=totals,
        )
