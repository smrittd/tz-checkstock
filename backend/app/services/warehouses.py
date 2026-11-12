from app.core.errors import DomainError
from app.db.base import utcnow
from app.db.uow import UnitOfWork
from app.models.warehouse import Warehouse
from app.schemas.warehouses import WarehouseInput, WarehouseOut


class WarehouseService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def warehouses(self, include_archived: bool = True):
        return await self.uow.warehouses.warehouses(include_archived)

    async def create_warehouse(self, data: WarehouseInput) -> dict:
        async with self.uow.transaction():
            return await self._save_warehouse(data.name)

    async def rename_warehouse(self, warehouse_id: int, data: WarehouseInput) -> dict:
        async with self.uow.transaction():
            return await self._save_warehouse(data.name, warehouse_id)

    async def archive_warehouse(self, warehouse_id: int) -> dict:
        async with self.uow.transaction():
            return await self._archive_warehouse(warehouse_id)

    async def get(self, warehouse_id: int, *, active: bool = False) -> Warehouse:
        warehouse = await self.uow.warehouses.warehouse(warehouse_id)
        if not warehouse:
            raise DomainError("warehouse_not_found", "Склад не найден.", 404)
        if active and warehouse.archived_at:
            raise DomainError(
                "warehouse_archived",
                "Склад в архиве. Выберите действующий склад.",
                warehouse_id=warehouse.id,
            )
        return warehouse

    async def _save_warehouse(self, name: str, warehouse_id: int | None = None) -> dict:
        name_key = name.casefold()
        duplicate = await self.uow.warehouses.warehouse_by_name(name_key)
        if duplicate and duplicate.id != warehouse_id:
            raise DomainError("warehouse_name_taken", "Склад с таким названием уже существует.")
        if warehouse_id is None:
            warehouse = Warehouse(name=name, name_key=name_key)
            self.uow.warehouses.add(warehouse)
        else:
            warehouse = await self.get(warehouse_id, active=True)
            warehouse.name = name
            warehouse.name_key = name_key
        await self.uow.warehouses.flush()
        return WarehouseOut.model_validate(warehouse).model_dump(mode="json")

    async def _archive_warehouse(self, warehouse_id: int) -> dict:
        warehouse = await self.get(warehouse_id)
        if warehouse.archived_at is None:
            warehouse.archived_at = utcnow()
        await self.uow.warehouses.flush()
        return WarehouseOut.model_validate(warehouse).model_dump(mode="json")
