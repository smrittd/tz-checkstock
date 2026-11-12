from datetime import datetime
from uuid import UUID

from app.schemas.common import OutputModel


class EventOut(OutputModel):
    id: int
    movement_id: UUID
    product_id: int
    action: str
    quantity: int
    source_name: str
    destination_name: str
    warehouse_id: int | None
    on_hand_delta: int
    reserved_delta: int
    created_at: datetime
