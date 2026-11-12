from app.core.errors import DomainError
from app.db.uow import UnitOfWork
from app.models.product import Product


class ProductService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def products(self):
        return await self.uow.products.products()

    async def get(self, product_id: int) -> Product:
        product = await self.uow.products.product(product_id)
        if not product:
            raise DomainError("product_not_found", "Товар не найден.", 404)
        return product
