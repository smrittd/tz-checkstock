import pytest
from sqlalchemy import func, select

from app.core.errors import DomainError
from app.db.uow import UnitOfWork
from app.models.balance import Balance
from app.models.event import Event
from app.models.movement import Movement
from app.schemas.movements import ReceiptInput
from app.services.movements import MovementService


async def test_receipt_without_http_commits_balance_and_journal(session_factory):
    data = ReceiptInput(product_id=1, warehouse_id=1, quantity=3)
    async with session_factory() as session:
        result = await MovementService(UnitOfWork(session)).receipt(data)
        assert result["quantity"] == 3
    async with session_factory() as session:
        assert (await session.get(Balance, (1, 1))).on_hand == 13
        assert await session.scalar(select(func.count()).select_from(Movement)) == 5
        assert await session.scalar(select(func.count()).select_from(Event)) == 5


async def test_failed_use_case_leaves_session_ready_for_retry(session_factory):
    async with session_factory() as session:
        service = MovementService(UnitOfWork(session))
        with pytest.raises(DomainError) as error:
            await service.receipt(ReceiptInput(product_id=999, warehouse_id=1, quantity=3))
        assert error.value.code == "product_not_found"
        assert not session.in_transaction()
        result = await service.receipt(ReceiptInput(product_id=1, warehouse_id=1, quantity=3))
        assert result["quantity"] == 3
    async with session_factory() as session:
        assert (await session.get(Balance, (1, 1))).on_hand == 13
