from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, utcnow


class Event(Base):
    """Append-only through the application; deltas reconcile every warehouse balance."""

    __tablename__ = "events"
    __table_args__ = (Index("ix_events_product_id_id", "product_id", "id"),)
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    movement_id: Mapped[UUID] = mapped_column(ForeignKey("movements.id"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    action: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[int]
    source_name: Mapped[str] = mapped_column(String(160))
    destination_name: Mapped[str] = mapped_column(String(160))
    warehouse_id: Mapped[int | None] = mapped_column(ForeignKey("warehouses.id"))
    on_hand_delta: Mapped[int] = mapped_column(BigInteger)
    reserved_delta: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
