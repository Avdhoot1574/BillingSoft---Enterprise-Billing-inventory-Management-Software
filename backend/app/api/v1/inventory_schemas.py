from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class StockAdjustmentIn(BaseModel):
    item_id: UUID
    warehouse_id: UUID
    quantity_delta: Decimal = Field(
        allow_inf_nan=False,
        max_digits=20,
        decimal_places=6,
    )
    unit_cost: Decimal = Field(default=0, ge=0)
    notes: str | None = None