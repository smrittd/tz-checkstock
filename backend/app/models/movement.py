from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Movement(Base):
    __tablename__ = "movements"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_movement_quantity"),
        CheckConstraint(
            "(kind = 'receipt' AND status = 'received') OR "
            "(kind = 'transfer' AND status IN ('in_transit', 'received')) OR "
            "(kind = 'fbs' AND status IN ('reserved', 'cancelled', 'in_transit', 'delivered')) OR "
            "(kind = 'fbo' AND status IN ('in_transit', 'received'))",
            name="ck_movement_state",
        ),
        CheckConstraint(
            "(kind = 'receipt' AND source_id IS NULL AND destination_id IS NOT NULL "
            "AND external_destination IS NULL) OR "
            "(kind = 'transfer' AND source_id IS NOT NULL AND destination_id IS NOT NULL "
            "AND source_id <> destination_id AND external_destination IS NULL) OR "
            "(kind IN ('fbs', 'fbo') AND source_id IS NOT NULL AND destination_id IS NULL "
            "AND external_destination IS NOT NULL)",
            name="ck_movement_route",
        ),
        Index("ix_movements_created_at", "created_at", "id"),
        Index("ix_movements_product_status", "product_id", "status"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    kind: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    quantity: Mapped[int]
    source_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    destination_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    external_destination: Mapped[str | None] = mapped_column(String(120))
    note: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
