"""Create inventory schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.Uuid(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("response", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
    )
    op.create_table(
        "seed_runs", sa.Column("name", sa.Text(), nullable=False), sa.PrimaryKeyConstraint("name")
    )
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "warehouses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("name_key", sa.String(length=120), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name_key"),
    )
    op.create_table(
        "balances",
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=False),
        sa.Column("on_hand", sa.BigInteger(), nullable=False),
        sa.Column("reserved", sa.BigInteger(), nullable=False),
        sa.CheckConstraint("on_hand >= 0", name="ck_balance_on_hand"),
        sa.CheckConstraint("reserved >= 0 AND reserved <= on_hand", name="ck_balance_reserved"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
        ),
        sa.PrimaryKeyConstraint("product_id", "warehouse_id"),
    )
    op.create_table(
        "movements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("destination_id", sa.Integer(), nullable=True),
        sa.Column("external_destination", sa.String(length=120), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "(kind = 'receipt' AND source_id IS NULL AND destination_id IS NOT NULL "
            "AND external_destination IS NULL) OR "
            "(kind = 'transfer' AND source_id IS NOT NULL AND destination_id IS NOT NULL "
            "AND source_id <> destination_id AND external_destination IS NULL) OR "
            "(kind IN ('fbs', 'fbo') AND source_id IS NOT NULL AND destination_id IS NULL "
            "AND external_destination IS NOT NULL)",
            name="ck_movement_route",
        ),
        sa.CheckConstraint(
            "(kind = 'receipt' AND status = 'received') OR "
            "(kind = 'transfer' AND status IN ('in_transit', 'received')) OR "
            "(kind = 'fbs' AND status IN ('reserved', 'cancelled', 'in_transit', 'delivered')) OR "
            "(kind = 'fbo' AND status IN ('in_transit', 'received'))",
            name="ck_movement_state",
        ),
        sa.CheckConstraint("quantity > 0", name="ck_movement_quantity"),
        sa.ForeignKeyConstraint(
            ["destination_id"],
            ["warehouses.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["warehouses.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_movements_created_at", "movements", ["created_at", "id"], unique=False)
    op.create_index(
        "ix_movements_product_status", "movements", ["product_id", "status"], unique=False
    )
    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("movement_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("source_name", sa.String(length=160), nullable=False),
        sa.Column("destination_name", sa.String(length=160), nullable=False),
        sa.Column("warehouse_id", sa.Integer(), nullable=True),
        sa.Column("on_hand_delta", sa.BigInteger(), nullable=False),
        sa.Column("reserved_delta", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["movement_id"],
            ["movements.id"],
        ),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
        ),
        sa.ForeignKeyConstraint(
            ["warehouse_id"],
            ["warehouses.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_movement_id"), "events", ["movement_id"], unique=False)
    op.create_index("ix_events_product_id_id", "events", ["product_id", "id"], unique=False)
    op.bulk_insert(
        sa.table("stores", sa.column("id", sa.Integer), sa.column("name", sa.String)),
        [{"id": 1, "name": "Демо-магазин"}],
    )


def downgrade():
    op.drop_index("ix_events_product_id_id", table_name="events")
    op.drop_index(op.f("ix_events_movement_id"), table_name="events")
    op.drop_table("events")
    op.drop_index("ix_movements_product_status", table_name="movements")
    op.drop_index("ix_movements_created_at", table_name="movements")
    op.drop_table("movements")
    op.drop_table("balances")
    op.drop_table("warehouses")
    op.drop_table("stores")
    op.drop_table("seed_runs")
    op.drop_table("products")
    op.drop_table("idempotency_records")
