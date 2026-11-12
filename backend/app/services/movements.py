from uuid import UUID

from app.core.errors import DomainError
from app.db.base import utcnow
from app.db.uow import UnitOfWork
from app.models.balance import Balance
from app.models.event import Event
from app.models.movement import Movement
from app.schemas.movements import (
    Action,
    Kind,
    MovementOut,
    ReceiptInput,
    ShipmentInput,
    Status,
    TransferInput,
)
from app.services.products import ProductService
from app.services.warehouses import WarehouseService

TRANSITIONS = {
    ("transfer", "receive"): ("in_transit", "received"),
    ("fbo", "receive"): ("in_transit", "received"),
    ("fbs", "ship"): ("reserved", "in_transit"),
    ("fbs", "cancel"): ("reserved", "cancelled"),
    ("fbs", "deliver"): ("in_transit", "delivered"),
}


def movement_json(movement: Movement) -> dict:
    return MovementOut.model_validate(movement).model_dump(mode="json")


def event_action(kind: str, action: str) -> str:
    suffix = {
        "receive": "received",
        "ship": "shipped",
        "cancel": "cancelled",
        "deliver": "delivered",
    }
    return f"{kind}_{suffix[action]}"


class MovementService:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow
        self.products = ProductService(uow)
        self.warehouses = WarehouseService(uow)

    async def movement(self, movement_id: UUID) -> Movement:
        movement = await self.uow.movements.movement(movement_id)
        if movement is None:
            raise DomainError("movement_not_found", "Операция не найдена.", 404)
        return movement

    async def movements(
        self,
        kind: Kind | None,
        status: Status | None,
        product_id: int | None,
        limit: int,
        offset: int,
    ) -> dict:
        items, total = await self.uow.movements.movements(kind, status, product_id, limit, offset)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    async def receipt(self, data: ReceiptInput) -> dict:
        async with self.uow.transaction():
            return await self.record_receipt(data)

    async def transfer(self, data: TransferInput) -> dict:
        async with self.uow.transaction():
            return await self._create_transfer(data)

    async def fbs(self, data: ShipmentInput) -> dict:
        async with self.uow.transaction():
            return await self._create_shipment(data, "fbs")

    async def fbo(self, data: ShipmentInput) -> dict:
        async with self.uow.transaction():
            return await self._create_shipment(data, "fbo")

    async def confirm(self, movement_id: UUID, action: Action) -> dict:
        async with self.uow.transaction():
            return await self._transition(movement_id, action)

    async def _balance_for(self, product_id: int, warehouse_id: int) -> Balance:
        balance = await self.uow.balances.balance(product_id, warehouse_id)
        if balance is None:
            balance = Balance(
                product_id=product_id, warehouse_id=warehouse_id, on_hand=0, reserved=0
            )
            self.uow.balances.add(balance)
            await self.uow.balances.flush()
        return balance

    async def _require_available(self, product_id: int, warehouse_id: int, quantity: int) -> None:
        balance = await self._balance_for(product_id, warehouse_id)
        available = balance.on_hand - balance.reserved
        if available >= quantity:
            return
        alternatives = [
            {
                "warehouse_id": warehouse.id,
                "warehouse_name": warehouse.name,
                "archived": warehouse.archived_at is not None,
                "available": stock.on_hand - stock.reserved,
            }
            for stock, warehouse in await self.uow.balances.alternative_balances(
                product_id, warehouse_id
            )
            if stock.on_hand > stock.reserved
        ]
        raise DomainError(
            "insufficient_stock",
            "На выбранном ФФ недостаточно доступного товара. "
            "Сначала переместите товар с другого ФФ или уменьшите количество.",
            warehouse_id=warehouse_id,
            requested=quantity,
            available=available,
            total_available=available + sum(item["available"] for item in alternatives),
            alternatives=alternatives,
        )

    async def _record_event(
        self,
        movement: Movement,
        action: str,
        source_name: str,
        destination_name: str,
        warehouse_id: int | None = None,
        on_hand_delta: int = 0,
        reserved_delta: int = 0,
    ) -> None:
        if warehouse_id is not None:
            balance = await self._balance_for(movement.product_id, warehouse_id)
            balance.on_hand += on_hand_delta
            balance.reserved += reserved_delta
        self.uow.events.add(
            Event(
                movement_id=movement.id,
                product_id=movement.product_id,
                action=action,
                quantity=movement.quantity,
                source_name=source_name,
                destination_name=destination_name,
                warehouse_id=warehouse_id,
                on_hand_delta=on_hand_delta,
                reserved_delta=reserved_delta,
            )
        )
        await self.uow.events.flush()

    async def record_receipt(self, data: ReceiptInput) -> dict:
        """Записать приход внутри уже открытой транзакции с блокировкой магазина.

        Вызывается из receipt и DemoService; commit выполняет владелец транзакции.
        """
        await self.products.get(data.product_id)
        warehouse = await self.warehouses.get(data.warehouse_id, active=True)
        movement = Movement(
            kind="receipt",
            status="received",
            product_id=data.product_id,
            quantity=data.quantity,
            destination_id=warehouse.id,
            note=data.note,
        )
        self.uow.movements.add(movement)
        await self.uow.movements.flush()
        await self._record_event(
            movement, "receipt", "Поставщик", warehouse.name, warehouse.id, data.quantity
        )
        return movement_json(movement)

    async def _create_transfer(self, data: TransferInput) -> dict:
        await self.products.get(data.product_id)
        source = await self.warehouses.get(data.source_id)
        destination = await self.warehouses.get(data.destination_id, active=True)
        if source.id == destination.id:
            raise DomainError("same_warehouse", "Для перемещения выберите другой склад.")
        await self._require_available(data.product_id, source.id, data.quantity)
        movement = Movement(
            kind="transfer",
            status="in_transit",
            product_id=data.product_id,
            quantity=data.quantity,
            source_id=source.id,
            destination_id=destination.id,
            note=data.note,
        )
        self.uow.movements.add(movement)
        await self.uow.movements.flush()
        await self._record_event(
            movement,
            "transfer_shipped",
            source.name,
            destination.name,
            source.id,
            -data.quantity,
        )
        return movement_json(movement)

    async def _create_shipment(self, data: ShipmentInput, kind: str) -> dict:
        await self.products.get(data.product_id)
        warehouse = await self.warehouses.get(data.warehouse_id, active=True)
        await self._require_available(data.product_id, warehouse.id, data.quantity)
        is_fbs = kind == "fbs"
        movement = Movement(
            kind=kind,
            status="reserved" if is_fbs else "in_transit",
            product_id=data.product_id,
            quantity=data.quantity,
            source_id=warehouse.id,
            external_destination=data.destination,
            note=data.note,
        )
        self.uow.movements.add(movement)
        await self.uow.movements.flush()
        await self._record_event(
            movement,
            "fbs_reserved" if is_fbs else "fbo_shipped",
            warehouse.name,
            data.destination,
            warehouse.id,
            on_hand_delta=0 if is_fbs else -data.quantity,
            reserved_delta=data.quantity if is_fbs else 0,
        )
        return movement_json(movement)

    async def _transition(self, movement_id: UUID, action: Action) -> dict:
        movement = await self.uow.movements.movement(movement_id)
        if movement is None:
            raise DomainError("movement_not_found", "Операция не найдена.", 404)
        states = TRANSITIONS.get((movement.kind, action))
        if states is None:
            raise DomainError("invalid_transition", "Это действие недоступно для данной операции.")
        previous, target = states
        # Repeating a completed action must not apply its stock changes again.
        already_applied = await self.uow.events.has_event(
            movement.id, event_action(movement.kind, action)
        )
        if already_applied:
            return movement_json(movement)
        if movement.status != previous:
            raise DomainError(
                "invalid_transition",
                "Операция уже в другом состоянии. Обновите список.",
                current_status=movement.status,
            )
        source = (await self.warehouses.get(movement.source_id)) if movement.source_id else None
        destination = (
            (await self.warehouses.get(movement.destination_id))
            if movement.destination_id
            else None
        )
        # Existing inbound transfers are accepted even if the recipient has since been archived.
        # This preserves their actual location; goods can subsequently be transferred out.
        warehouse_id = None
        on_hand_delta = reserved_delta = 0
        source_name = source.name if source else "Поставщик"
        destination_name = destination.name if destination else movement.external_destination
        if movement.kind == "transfer":
            warehouse_id, on_hand_delta = destination.id, movement.quantity
        elif movement.kind == "fbs" and action in ("ship", "cancel"):
            warehouse_id, reserved_delta = source.id, -movement.quantity
            if action == "ship":
                on_hand_delta = -movement.quantity
            else:
                source_name, destination_name = f"Резерв FBS: {destination_name}", source.name
        elif movement.kind == "fbs" and action == "deliver":
            source_name = "В пути к клиенту"
        elif movement.kind == "fbo":
            source_name = "В пути на маркетплейс"
        movement.status = target
        movement.updated_at = utcnow()
        await self._record_event(
            movement,
            event_action(movement.kind, action),
            source_name,
            destination_name,
            warehouse_id,
            on_hand_delta,
            reserved_delta,
        )
        return movement_json(movement)
