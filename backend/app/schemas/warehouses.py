from datetime import datetime

from app.schemas.common import InputModel, Name, OutputModel


class WarehouseInput(InputModel):
    name: Name


class WarehouseOut(OutputModel):
    id: int
    name: str
    archived_at: datetime | None
    created_at: datetime
