from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PaymentAllocationIn(BaseModel):
    sales_invoice_id: UUID | None = None
    purchase_bill_id: UUID | None = None
    amount: Decimal = Field(gt=0)


class PaymentCreateIn(BaseModel):
    party_id: UUID | None = None
    payment_account_id: UUID
    direction: Literal["in", "out"]
    payment_date: date
    amount: Decimal = Field(gt=0)
    method: Literal["cash", "bank_transfer", "upi", "card", "cheque", "other"] = "cash"
    reference_number: str | None = None
    notes: str | None = None
    allocations: list[PaymentAllocationIn] = Field(default_factory=list)


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