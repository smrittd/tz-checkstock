from app.db.uow import UnitOfWork
from app.models.product import Product
from app.models.seed_run import SeedRun
from app.models.warehouse import Warehouse
from app.schemas.movements import ReceiptInput
from app.services.movements import MovementService


class DemoService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        self.movements = MovementService(uow)

    async def seed_demo(self) -> bool:
        """Загрузить демо-набор один раз; приход проходит через обычный учёт."""
        async with self.uow.transaction():
            if await self.uow.system.seed_run("demo-v1"):
                return False
            warehouses = []
            for name in ("Север", "Юг"):
                warehouse = await self.uow.warehouses.warehouse_by_name(name.casefold())
                if warehouse is None:
                    warehouse = Warehouse(name=name, name_key=name.casefold())
                    self.uow.warehouses.add(warehouse)
                    await self.uow.warehouses.flush()
                warehouses.append(warehouse)
            for sku, name, quantities in (
                ("SKU-101", "Органайзер", (10, 6)),
                ("SKU-102", "Контейнер", (5, 0)),
                ("SKU-103", "Корзина", (0, 4)),
            ):
                product = await self.uow.products.product_by_sku(sku)
                if product is None:
                    product = Product(sku=sku, name=name)
                    self.uow.products.add(product)
                    await self.uow.products.flush()
                for warehouse, quantity in zip(warehouses, quantities, strict=True):
                    if quantity:
                        await self.movements.record_receipt(
                            ReceiptInput(
                                product_id=product.id,
                                warehouse_id=warehouse.id,
                                quantity=quantity,
                                note="Тестовый приход из ТЗ",
                            ),
                        )
            self.uow.system.add(SeedRun(name="demo-v1"))
            return True
