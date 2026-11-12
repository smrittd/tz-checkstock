from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import Field

from app.schemas.common import Identifier, InputModel, Name, OutputModel, Quantity


class MovementInput(InputModel):
    product_id: Identifier
    quantity: Quantity
    note: str = Field(default="", max_length=500)


class ReceiptInput(MovementInput):
    warehouse_id: Identifier


class TransferInput(MovementInput):
    source_id: Identifier
    destination_id: Identifier


class ShipmentInput(MovementInput):
    warehouse_id: Identifier
    destination: Name


class Kind(StrEnum):
    receipt = "receipt"
    transfer = "transfer"
    fbs = "fbs"
    fbo = "fbo"


class Status(StrEnum):
    received = "received"
    in_transit = "in_transit"
    reserved = "reserved"
    cancelled = "cancelled"
    delivered = "delivered"


class Action(StrEnum):
    receive = "receive"
    ship = "ship"
    cancel = "cancel"
    deliver = "deliver"


class MovementOut(OutputModel):
    id: UUID
    kind: Kind
    status: Status
    product_id: int
    quantity: int
    source_id: int | None
    destination_id: int | None
    external_destination: str | None
    note: str
    created_at: datetime
    updated_at: datetime
