import pytest
from conftest import assert_conservation
from sqlalchemy import func, select

from app.models.event import Event
from app.models.movement import Movement
from app.seed import seed_demo


async def test_seed_has_exact_stock_and_zero_cells(client, stock, session_factory):
    inventory = await assert_conservation(client)
    assert inventory["store"] == "Демо-магазин"
    assert inventory["totals"]["total_received"] == 25
    assert [(p["sku"], p["name"]) for p in inventory["products"]] == [
        ("SKU-101", "Органайзер"),
        ("SKU-102", "Контейнер"),
        ("SKU-103", "Корзина"),
    ]
    assert [[(await stock(p, w))["on_hand"] for w in (1, 2)] for p in (1, 2, 3)] == [
        [10, 6],
        [5, 0],
        [0, 4],
    ]
    async with session_factory() as session:
        assert (await seed_demo(session)) is False
        assert (await session.scalar(select(func.count()).select_from(Movement))) == 4
        assert (await session.scalar(select(func.count()).select_from(Event))) == 4


async def test_receipt_updates_only_selected_product_and_warehouse(write, stock):
    movement = await write("/receipts", {"product_id": 2, "warehouse_id": 2, "quantity": 7})
    assert movement["status"] == "received"
    assert (await stock(2, 2))["available"] == 7
    assert (await stock(2, 1))["on_hand"] == 5
    assert (await stock(1, 2))["on_hand"] == 6


async def test_fbs_reserve_ship_deliver_and_repeat(write, stock, client):
    order = await write(
        "/fbs", {"product_id": 1, "warehouse_id": 1, "quantity": 4, "destination": "Заказ 101"}
    )
    assert (await stock()) == {"warehouse_id": 1, "on_hand": 10, "reserved": 4, "available": 6}
    await write(f"/movements/{order['id']}/ship", status=200)
    assert (await stock()) == {"warehouse_id": 1, "on_hand": 6, "reserved": 0, "available": 6}
    assert (await assert_conservation(client))["totals"]["fbs_in_transit"] == 4
    await write(f"/movements/{order['id']}/ship", status=200)
    await write(f"/movements/{order['id']}/deliver", status=200)
    await write(f"/movements/{order['id']}/ship", status=200)
    await write(f"/movements/{order['id']}/deliver", status=200)
    totals = (await assert_conservation(client))["totals"]
    assert totals["fbs_in_transit"] == 0
    assert totals["delivered"] == 4
    assert (await client.get("/api/v1/history", params={"movement_id": order["id"]})).json()[
        "total"
    ] == 3


async def test_cancellation_frees_reserve_without_receipt(write, stock):
    order = await write(
        "/fbs", {"product_id": 1, "warehouse_id": 1, "quantity": 10, "destination": "Заказ 102"}
    )
    assert (await stock())["available"] == 0
    await write(f"/movements/{order['id']}/cancel", status=200)
    await write(f"/movements/{order['id']}/cancel", status=200)
    assert (await stock())["on_hand"] == (await stock())["available"] == 10
    error = await write(f"/movements/{order['id']}/ship", status=409)
    assert error["error"]["code"] == "invalid_transition"


async def test_transfer_has_separate_transit_then_receives_once(write, stock, client):
    transfer = await write(
        "/transfers", {"product_id": 1, "source_id": 1, "destination_id": 2, "quantity": 3}
    )
    assert (await stock())["on_hand"] == 7
    assert (await stock(1, 2))["on_hand"] == 6
    assert (await assert_conservation(client))["totals"]["transfer_in_transit"] == 3
    for _ in range(2):
        await write(f"/movements/{transfer['id']}/receive", status=200)
    assert (await stock(1, 2))["on_hand"] == 9
    assert (await assert_conservation(client))["totals"]["transfer_in_transit"] == 0


async def test_fbo_leaves_warehouse_and_is_accounted_at_marketplace(write, stock, client):
    shipment = await write(
        "/fbo",
        {"product_id": 1, "warehouse_id": 1, "quantity": 5, "destination": "Маркетплейс Казань"},
    )
    assert (await stock())["on_hand"] == 5
    assert (await assert_conservation(client))["totals"]["fbo_in_transit"] == 5
    for _ in range(2):
        await write(f"/movements/{shipment['id']}/receive", status=200)
    inventory = await assert_conservation(client)
    assert inventory["totals"]["fbo_in_transit"] == 0
    assert inventory["totals"]["at_marketplace"] == 5
    assert inventory["products"][0]["marketplaces"] == [
        {"destination": "Маркетплейс Казань", "quantity": 5},
    ]


@pytest.mark.parametrize("endpoint", ["fbs", "fbo", "transfers"])
async def test_shortage_on_selected_warehouse_even_with_sufficient_total(endpoint, write, stock):
    payload = {"product_id": 1, "quantity": 12}
    if endpoint == "transfers":
        payload.update(source_id=1, destination_id=2)
    else:
        payload.update(warehouse_id=1, destination="Получатель")
    result = (await write(f"/{endpoint}", payload, status=409))["error"]
    assert result["code"] == "insufficient_stock"
    assert result["context"]["available"] == 10
    assert result["context"]["total_available"] == 16
    assert result["context"]["alternatives"] == [
        {"warehouse_id": 2, "warehouse_name": "Юг", "available": 6, "archived": False},
    ]
    assert (await stock())["on_hand"] == 10
    assert (await stock(1, 2))["on_hand"] == 6


@pytest.mark.parametrize("endpoint", ["fbs", "fbo", "transfers"])
async def test_reserved_goods_cannot_be_spent(endpoint, write, stock):
    await write(
        "/fbs", {"product_id": 1, "warehouse_id": 1, "quantity": 8, "destination": "Клиент"}
    )
    payload = {"product_id": 1, "quantity": 3}
    if endpoint == "transfers":
        payload.update(source_id=1, destination_id=2)
    else:
        payload.update(warehouse_id=1, destination="Другой клиент")
    error = (await write(f"/{endpoint}", payload, status=409))["error"]
    assert error["context"]["available"] == 2
    assert (await stock())["reserved"] == 8


async def test_shortage_can_be_resolved_by_explicit_transfer(write, stock):
    payload = {"product_id": 1, "warehouse_id": 1, "quantity": 12, "destination": "Клиент"}
    await write("/fbs", payload, status=409)
    transfer = await write(
        "/transfers", {"product_id": 1, "source_id": 2, "destination_id": 1, "quantity": 2}
    )
    await write(f"/movements/{transfer['id']}/receive", status=200)
    await write("/fbs", payload)
    assert (await stock())["reserved"] == 12
    assert (await stock())["available"] == 0


async def test_end_to_end_mixed_warehouse_scenario(write, stock, client):
    await write("/receipts", {"product_id": 1, "warehouse_id": 1, "quantity": 5})
    order = await write(
        "/fbs", {"product_id": 1, "warehouse_id": 1, "quantity": 3, "destination": "Заказ 1"}
    )
    transfer = await write(
        "/transfers", {"product_id": 1, "source_id": 1, "destination_id": 2, "quantity": 4}
    )
    shipment = await write(
        "/fbo", {"product_id": 1, "warehouse_id": 2, "quantity": 2, "destination": "Маркетплейс"}
    )
    await write(f"/movements/{order['id']}/ship", status=200)
    await write(f"/movements/{transfer['id']}/receive", status=200)
    await write(f"/movements/{shipment['id']}/receive", status=200)
    assert (await stock())["on_hand"] == 8
    assert (await stock(1, 2))["on_hand"] == 8
    totals = (await assert_conservation(client))["products"][0]["totals"]
    assert totals["total_received"] == 21
    assert totals["fbs_in_transit"] == 3
    assert totals["at_marketplace"] == 2
