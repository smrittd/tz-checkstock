from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError, OperationalError

from app.api.dependencies import get_session
from app.models.event import Event
from app.models.movement import Movement
from app.services.movements import MovementService


@pytest.mark.parametrize("quantity", [0, -1, 1.5, True, "3", 1_000_001, None])
async def test_quantity_is_a_strict_positive_integer(quantity, write):
    error = await write(
        "/receipts", {"product_id": 1, "warehouse_id": 1, "quantity": quantity}, status=422
    )
    assert error["error"]["code"] == "validation_error"


@pytest.mark.parametrize("name", ["", "   ", "x" * 121])
async def test_invalid_warehouse_name(name, write):
    await write("/warehouses", {"name": name}, status=422)


async def test_creation_needs_no_header_and_unknown_fields_are_rejected(client, write, stock):
    payload = {"product_id": 1, "warehouse_id": 1, "quantity": 1}
    assert (await client.post("/api/v1/receipts", json=payload)).status_code == 201
    assert (await stock())["on_hand"] == 11
    await write("/receipts", payload | {"unexpected": "field"}, status=422)


async def test_swagger_has_no_request_key_field(client):
    schema = (await client.get("/openapi.json")).json()
    for path in schema["paths"].values():
        for operation in path.values():
            assert all(
                p["name"].lower() != "idempotency-key" for p in operation.get("parameters", [])
            )
    docs = (await client.get("/docs")).text
    assert "SwaggerUIBundle" in docs
    assert "idempotency-key.js" not in docs


@pytest.mark.parametrize("field", ["product_id", "warehouse_id"])
async def test_missing_entity_returns_404_without_side_effects(field, write, stock):
    payload = {"product_id": 1, "warehouse_id": 1, "quantity": 1, field: 999}
    await write("/receipts", payload, status=404)
    assert (await stock())["on_hand"] == 10


async def test_invalid_routes_and_transitions(write, client):
    await write(
        "/transfers",
        {"product_id": 1, "source_id": 1, "destination_id": 1, "quantity": 1},
        status=409,
    )
    await write(f"/movements/{uuid4()}/receive", status=404)
    assert (await client.get(f"/api/v1/movements/{uuid4()}")).status_code == 404
    assert (await client.get("/api/v1/movements/not-a-uuid")).status_code == 422
    await write("/warehouses/999", method="DELETE", status=404)
    receipt = await write("/receipts", {"product_id": 1, "warehouse_id": 1, "quantity": 1})
    await write(f"/movements/{receipt['id']}/receive", status=409)
    order = await write(
        "/fbs", {"product_id": 1, "warehouse_id": 1, "quantity": 1, "destination": "Клиент"}
    )
    await write(f"/movements/{order['id']}/deliver", status=409)
    await write(f"/movements/{order['id']}/ship", status=200)
    await write(f"/movements/{order['id']}/cancel", status=409)


@pytest.mark.parametrize(
    "endpoint,payload",
    [
        ("receipts", {"product_id": 1, "warehouse_id": 1, "quantity": 2}),
        ("fbs", {"product_id": 1, "warehouse_id": 1, "quantity": 2, "destination": "Клиент"}),
        ("fbo", {"product_id": 1, "warehouse_id": 1, "quantity": 2, "destination": "Маркетплейс"}),
        ("transfers", {"product_id": 1, "source_id": 1, "destination_id": 2, "quantity": 2}),
    ],
)
async def test_repeated_creation_is_a_new_operation(endpoint, payload, write, client):
    original = await write(f"/{endpoint}", payload)
    repeated = await write(f"/{endpoint}", payload)
    assert original["id"] != repeated["id"]
    page = (await client.get("/api/v1/movements", params={"kind": original["kind"]})).json()
    assert {original["id"], repeated["id"]} <= {item["id"] for item in page["items"]}


async def test_atomic_rollback_including_journal_and_balance(client, monkeypatch, session_factory):
    original = MovementService._record_event

    async def fail_after_event(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError("Simulated failure after writing journal and balance")

    monkeypatch.setattr(MovementService, "_record_event", fail_after_event)
    with pytest.raises(RuntimeError, match="Simulated failure"):
        await client.post(
            "/api/v1/receipts",
            json={"product_id": 1, "warehouse_id": 1, "quantity": 8},
        )
    async with session_factory() as session:
        assert (await session.scalar(select(func.count()).select_from(Event))) == 4
        assert (await session.scalar(select(func.count()).select_from(Movement))) == 4
    assert (await client.get("/api/v1/inventory")).json()["totals"]["on_hand"] == 25


@pytest.mark.parametrize("on_hand,reserved", [(-1, 0), (1, 2), (1, -1)])
async def test_database_constraints_protect_balances(session_factory, on_hand, reserved):
    with pytest.raises(IntegrityError):
        async with session_factory.begin() as session:
            await session.execute(
                text(
                    "UPDATE balances SET on_hand=:h, reserved=:r "
                    "WHERE product_id=1 AND warehouse_id=1"
                ),
                {"h": on_hand, "r": reserved},
            )


async def test_history_and_movements_filters_and_pagination(client, write):
    order = await write(
        "/fbs", {"product_id": 2, "warehouse_id": 1, "quantity": 1, "destination": "Клиент"}
    )
    assert (await client.get("/api/v1/products")).json()[0]["sku"] == "SKU-101"
    page = (
        await client.get("/api/v1/movements?kind=fbs&status=reserved&product_id=2&limit=1")
    ).json()
    assert page["total"] == 1
    assert page["items"][0]["id"] == order["id"]
    assert (await client.get("/api/v1/movements?kind=fbs&offset=1")).json()["items"] == []
    history = (await client.get("/api/v1/history?product_id=2&limit=1")).json()
    assert history["total"] == 2
    assert len(history["items"]) == 1
    assert history["items"][0]["source_name"] == "Север"
    assert history["items"][0]["quantity"] == 1
    assert (await client.get("/api/v1/history?offset=100")).json()["items"] == []
    assert (await client.get("/api/v1/movements?status=invalid")).status_code == 422
    assert (await client.get("/api/v1/history?limit=101")).status_code == 422
    assert (await client.get("/api/v1/history?offset=-1")).status_code == 422


@pytest.mark.parametrize(
    "error",
    [
        OperationalError("test", {}, Exception("Connection unavailable")),
        ConnectionRefusedError("Connection refused"),
        TimeoutError("Connection timeout"),
    ],
)
async def test_health_endpoints_and_database_outage(client, application, error):
    assert (await client.get("/health/live")).json() == {"status": "ok"}
    assert (await client.get("/health/ready")).json() == {"status": "ok"}

    async def unavailable():
        raise error

    application.dependency_overrides[get_session] = unavailable
    response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"
    assert (await client.get("/health/live")).status_code == 200
