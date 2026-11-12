from sqlalchemy import select

from app.models.product import Product
from app.repositories.base import BaseRepository


class ProductsRepository(BaseRepository):
    async def product(self, product_id: int) -> Product | None:
        return await self._session.get(Product, product_id)

    async def product_by_sku(self, sku: str) -> Product | None:
        return await self._session.scalar(select(Product).where(Product.sku == sku))

    async def products(self) -> list[Product]:
        return list(await self._session.scalars(select(Product).order_by(Product.sku)))
