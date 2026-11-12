from app.schemas.common import OutputModel


class ProductOut(OutputModel):
    id: int
    sku: str
    name: str
