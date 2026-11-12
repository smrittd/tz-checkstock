from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SeedRun(Base):
    __tablename__ = "seed_runs"
    name: Mapped[str] = mapped_column(Text, primary_key=True)
