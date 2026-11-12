import asyncio

import pytest
from conftest import assert_conservation
from sqlalchemy import func, select, text

from app.models.event import Event
from app.models.movement import Movement
from app.models.store import Store
from app.services.movements import MovementService


async def concurrent_requests(client, requests):
    barrier = asyncio.Barrier(len(requests))

    async def execute(request):
        path, payload = request
        async with asyncio.timeout(10):
            await barrier.wait()
            return await client.post(f"/api/v1{path}", json=payload)

    # One event loop and independent request sessions, as in a single Uvicorn worker.
    return await asyncio.gather(*(execute(request) for request in requests))


async def test_competing_reservations_cannot_oversell(client, stock):
    responses = await concurrent_requests(
        client,
        [
            (
                "/fbs",
                {
                    "product_id": 1,
                    "warehouse_id": 1,
                    "quantity": 10,
                    "destination": f"Клиент {index}",
                },
            )
            for index in range(4)
        ],
    )
    assert sorted(response.status_code for response in responses) == [201, 409, 409, 409]
    assert (await stock())["reserved"] == 10
    assert (await stock())["available"] == 0
    await assert_conservation(client)


async def test_concurrent_receipts_do_not_lose_stock_updates(client, stock):
    payload = {"product_id": 1, "warehouse_id": 1, "quantity": 7}
    responses = await concurrent_requests(client, [("/receipts", payload) for _ in range(4)])
    assert all(response.status_code == 201 for response in responses)
    assert len({response.json()["id"] for response in responses}) == 4
    assert (await stock())["on_hand"] == 38
    await assert_conservation(client)


async def test_concurrent_ship_and_cancel_has_one_winner(write, client, stock):
    order = await write(
        "/fbs",
        {
            "product_id": 1,
            "warehouse_id": 1,
            "quantity": 4,
            "destination": "Клиент",
        },
    )
    responses = await concurrent_requests(
        client,
        [(f"/movements/{order['id']}/{action}", None) for action in ("ship", "cancel")],
    )
    assert sorted(response.status_code for response in responses) == [200, 409]
    final = (await client.get(f"/api/v1/movements/{order['id']}")).json()
    assert (await stock())["reserved"] == 0
    assert (await stock())["on_hand"] == (6 if final["status"] == "in_transit" else 10)
    await assert_conservation(client)


async def test_concurrent_confirmation_does_not_duplicate(write, client, stock):
    transfer = await write(
        "/transfers",
        {
            "product_id": 1,
            "source_id": 1,
            "destination_id": 2,
            "quantity": 3,
        },
    )
    responses = await concurrent_requests(
        client, [(f"/movements/{transfer['id']}/receive", None) for _ in range(4)]
    )
    assert all(response.status_code == 200 for response in responses)
    assert (await stock(1, 2))["on_hand"] == 9
    history = (await client.get("/api/v1/history", params={"movement_id": transfer["id"]})).json()
    assert history["total"] == 2


async def test_database_lock_wait_does_not_block_other_requests(client, session_factory):
    pending = None
    try:
        async with session_factory.begin() as blocker:
            # Bound a regression even if a blocking driver accidentally stalls the event loop.
            await blocker.execute(text("SET LOCAL idle_in_transaction_session_timeout = '5s'"))
            blocker_pid = await blocker.scalar(text("SELECT pg_backend_pid()"))
            await blocker.execute(select(Store).where(Store.id == 1).with_for_update())
            pending = asyncio.create_task(
                client.post(
                    "/api/v1/fbs",
                    json={
                        "product_id": 1,
                        "warehouse_id": 1,
                        "quantity": 1,
                        "destination": "Клиент",
                    },
                )
            )
            # Observe an actual PostgreSQL lock wait rather than relying on an arbitrary sleep.
            async with asyncio.timeout(3), session_factory() as observer:
                while not await observer.scalar(
                    text(
                        "SELECT EXISTS (SELECT 1 FROM pg_stat_activity "
                        "WHERE datname = current_database() AND :pid = ANY(pg_blocking_pids(pid)))"
                    ),
                    {"pid": blocker_pid},
                ):
                    await asyncio.sleep(0.01)
                assert not pending.done()
                live = await asyncio.wait_for(client.get("/health/live"), timeout=1)
                products = await asyncio.wait_for(client.get("/api/v1/products"), timeout=1)
                assert live.status_code == products.status_code == 200
                assert not pending.done()
        response = await asyncio.wait_for(pending, timeout=3)
        assert response.status_code == 201, response.text
        await assert_conservation(client)
    finally:
        if pending is not None:
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)


async def test_cancelled_request_rolls_back_and_can_be_retried(
    client,
    session_factory,
    monkeypatch,
    write,
):
    flushed = asyncio.Event()
    original = MovementService._record_event

    async def pause_after_flush(*args, **kwargs):
        await original(*args, **kwargs)
        flushed.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(MovementService, "_record_event", pause_after_flush)
    payload = {"product_id": 1, "warehouse_id": 1, "quantity": 8}
    pending = asyncio.create_task(
        client.post(
            "/api/v1/receipts",
            json=payload,
        )
    )
    try:
        await asyncio.wait_for(flushed.wait(), timeout=3)
        pending.cancel()
        with pytest.raises(asyncio.CancelledError):
            await pending
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Event)) == 4
        assert await session.scalar(select(func.count()).select_from(Movement)) == 4
    assert (await assert_conservation(client))["totals"]["on_hand"] == 25
    monkeypatch.setattr(MovementService, "_record_event", original)
    await write("/receipts", payload)
    assert (await assert_conservation(client))["totals"]["on_hand"] == 33
