import pytest


async def test_create_rename_and_archive_preserves_identity_and_history(write, client, stock):
    warehouse = await write("/warehouses", {"name": "  Запад  "})
    assert warehouse["name"] == "Запад"
    assert (await stock(1, warehouse["id"]))["on_hand"] == 0
    receipt = await write(
        "/receipts", {"product_id": 1, "warehouse_id": warehouse["id"], "quantity": 7}
    )
    renamed = await write(
        f"/warehouses/{warehouse['id']}", {"name": "Восток"}, method="PATCH", status=200
    )
    assert renamed["id"] == warehouse["id"]
    event = (await client.get("/api/v1/history", params={"movement_id": receipt["id"]})).json()[
        "items"
    ][0]
    assert event["destination_name"] == "Запад"
    archived = await write(f"/warehouses/{warehouse['id']}", method="DELETE", status=200)
    repeated = await write(f"/warehouses/{warehouse['id']}", method="DELETE", status=200)
    assert archived["archived_at"] == repeated["archived_at"]
    assert (await stock(1, warehouse["id"]))["on_hand"] == 7
    assert len((await client.get("/api/v1/warehouses?include_archived=false")).json()) == 2
    assert len((await client.get("/api/v1/warehouses")).json()) == 3


@pytest.mark.parametrize("endpoint", ["receipts", "fbs", "fbo", "transfers"])
async def test_archived_warehouse_rejects_new_inbound_and_orders(endpoint, write):
    await write("/warehouses/1", method="DELETE", status=200)
    payload = {"product_id": 1, "quantity": 1}
    if endpoint == "transfers":
        payload.update(source_id=2, destination_id=1)
    else:
        payload["warehouse_id"] = 1
        if endpoint != "receipts":
            payload["destination"] = "Получатель"
    assert (await write(f"/{endpoint}", payload, status=409))["error"][
        "code"
    ] == "warehouse_archived"


async def test_archive_retains_reserve_allows_completion_and_evacuation(write, stock):
    order = await write(
        "/fbs", {"product_id": 1, "warehouse_id": 1, "quantity": 4, "destination": "Клиент"}
    )
    await write("/warehouses/1", method="DELETE", status=200)
    assert (await stock())["reserved"] == 4
    await write(f"/movements/{order['id']}/ship", status=200)
    transfer = await write(
        "/transfers", {"product_id": 1, "source_id": 1, "destination_id": 2, "quantity": 6}
    )
    await write(f"/movements/{transfer['id']}/receive", status=200)
    assert (await stock())["on_hand"] == (await stock())["reserved"] == 0
    assert (await stock(1, 2))["on_hand"] == 12


async def test_transfer_already_in_transit_can_arrive_at_archived_warehouse(write, stock):
    transfer = await write(
        "/transfers", {"product_id": 1, "source_id": 1, "destination_id": 2, "quantity": 3}
    )
    await write("/warehouses/2", method="DELETE", status=200)
    await write(f"/movements/{transfer['id']}/receive", status=200)
    assert (await stock(1, 2))["on_hand"] == 9
    await write("/transfers", {"product_id": 1, "source_id": 2, "destination_id": 1, "quantity": 9})
    assert (await stock(1, 2))["on_hand"] == 0


async def test_warehouse_name_is_unique_case_insensitive_even_in_archive(write):
    await write("/warehouses", {"name": " север "}, status=409)
    await write("/warehouses/1", method="DELETE", status=200)
    await write("/warehouses", {"name": "СЕВЕР"}, status=409)
    await write("/warehouses/2", {"name": "север"}, method="PATCH", status=409)


@pytest.mark.parametrize("name", ["ß" * 120, "ΐ" * 120])
async def test_valid_unicode_name_can_expand_when_normalized(write, name):
    warehouse = await write("/warehouses", {"name": name})
    assert warehouse["name"] == name
    await write("/warehouses", {"name": name}, status=409)
