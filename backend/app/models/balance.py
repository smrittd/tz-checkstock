from sqlalchemy import BigInteger, CheckConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Balance(Base):
    __tablename__ = "balances"
    __table_args__ = (
        CheckConstraint("on_hand >= 0", name="ck_balance_on_hand"),
        CheckConstraint("reserved >= 0 AND reserved <= on_hand", name="ck_balance_reserved"),
    )
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), primary_key=True)
    on_hand: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved: Mapped[int] = mapped_column(BigInteger, default=0)
