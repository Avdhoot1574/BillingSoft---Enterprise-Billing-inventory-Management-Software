from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PaymentAllocationIn(BaseModel):
    sales_invoice_id: UUID | None = None
    purchase_bill_id: UUID | None = None
    amount: Decimal = Field(gt=0, max_digits=17, decimal_places=2)


class PaymentCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    party_id: UUID | None = None
    payment_account_id: UUID
    direction: Literal["in", "out"]
    payment_date: date
    amount: Decimal = Field(gt=0, max_digits=17, decimal_places=2)
    method: Literal["cash", "bank_transfer", "upi", "card", "cheque", "other"] = "cash"
    reference_number: str | None = None
    notes: str | None = None
    allocations: list[PaymentAllocationIn] = Field(default_factory=list)


    @model_validator(mode="after")
    def validate_allocations(self):
        seen = set()
        for allocation in self.allocations:
            target = allocation.sales_invoice_id if self.direction == "in" else allocation.purchase_bill_id
            other = allocation.purchase_bill_id if self.direction == "in" else allocation.sales_invoice_id
            if not target or other:
                raise ValueError("Allocation document must match payment direction")
            if target in seen:
                raise ValueError("Duplicate allocation document")
            seen.add(target)
        if sum(a.amount for a in self.allocations) > self.amount:
            raise ValueError("Allocations cannot exceed payment amount")
        return self


class PaymentOut(BaseModel):
    id: UUID
    payment_number: str
    party_id: UUID | None
    payment_account_id: UUID
    direction: str
    payment_date: date
    amount: Decimal
    method: str
    status: str
    reference_number: str | None
    notes: str | None