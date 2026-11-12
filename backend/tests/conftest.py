import os

import pytest
from alembic import command
from alembic.config import Config
from httpx2 import ASGITransport, AsyncClient
from sqlalchemy import make_url, text

from app.db.session import create_database_engine
from app.main import create_app
from app.seed import seed_demo


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(scope="session")
async def application(anyio_backend):
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must point to a dedicated database ending with _test")
    engine = create_database_engine(url)

    def migrate(connection):
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "head")
        command.check(config)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()

    instance = create_app(url)
    # ASGITransport does not run lifespan. Exercise the real pool startup and shutdown here.
    async with instance.router.lifespan_context(instance):
        yield instance


@pytest.fixture
def session_factory(application):
    return application.state.session_factory


@pytest.fixture(autouse=True)
async def database(session_factory, application):
    async with session_factory.begin() as session:
        await session.execute(
            text(
                "TRUNCATE events, movements, balances, products, "
                "warehouses, seed_runs RESTART IDENTITY CASCADE"
            )
        )
    async with session_factory() as session:
        await seed_demo(session)
    try:
        yield
    finally:
        application.dependency_overrides.clear()
        # Independently reconcile every cached balance with its journal entries.
        async with session_factory() as session:
            mismatches = (
                await session.execute(
                    text("""
                SELECT b.product_id, b.warehouse_id
                FROM balances b
                LEFT JOIN events e
                  ON e.product_id = b.product_id AND e.warehouse_id = b.warehouse_id
                GROUP BY b.product_id, b.warehouse_id, b.on_hand, b.reserved
                HAVING b.on_hand != COALESCE(SUM(e.on_hand_delta), 0)
                    OR b.reserved != COALESCE(SUM(e.reserved_delta), 0)
            """)
                )
            ).all()
            assert not mismatches, "Balance and journal diverged"


@pytest.fixture
async def client(application):
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://test"
    ) as client:
        yield client


async def assert_conservation(client: AsyncClient) -> dict:
    response = await client.get("/api/v1/inventory")
    assert response.status_code == 200, response.text
    result = response.json()
    for product in result["products"]:
        totals = product["totals"]
        assert totals["available"] == totals["on_hand"] - totals["reserved"]
        assert totals["total_received"] == sum(
            totals[field]
            for field in (
                "on_hand",
                "transfer_in_transit",
                "fbs_in_transit",
                "fbo_in_transit",
                "at_marketplace",
                "delivered",
            )
        )
        for stock in product["warehouses"]:
            assert 0 <= stock["reserved"] <= stock["on_hand"]
            assert stock["available"] == stock["on_hand"] - stock["reserved"]
        for field in ("on_hand", "reserved", "available"):
            assert totals[field] == sum(stock[field] for stock in product["warehouses"])
    for field, total in result["totals"].items():
        assert total == sum(product["totals"][field] for product in result["products"])
    return result


@pytest.fixture
def write(client):
    async def request(path, data=None, *, status=201, method="POST"):
        response = await client.request(
            method,
            f"/api/v1{path}",
            json=data,
        )
        assert response.status_code == status, response.text
        await assert_conservation(client)
        return response.json()

    return request


@pytest.fixture
def stock(client):
    async def get(product_id=1, warehouse_id=1):
        inventory = await assert_conservation(client)
        product = next(item for item in inventory["products"] if item["id"] == product_id)
        return next(item for item in product["warehouses"] if item["warehouse_id"] == warehouse_id)

    return get
