from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PurchaseBillLineCreate(BaseModel):
    id: UUID | None = None
    item_id: UUID | None = None
    item_name: str = Field(min_length=1, max_length=250)
    hsn_sac: str | None = None
    unit_name: str = Field(min_length=1, max_length=50)
    quantity: Decimal = Field(gt=0)
    unit_cost: Decimal = Field(ge=0)
    discount_amount: Decimal = Field(default=0, ge=0)
    tax_rate_percent: Decimal = Field(default=0, ge=0, le=100)
    warehouse_id: UUID | None = None


class PurchaseBillCreate(BaseModel):
    party_id: UUID
    bill_date: date
    due_date: date | None = None
    supplier_invoice_number: str | None = Field(default=None, max_length=100)
    supplier_name_snapshot: str = Field(min_length=1, max_length=250)
    supplier_gstin_snapshot: str | None = Field(default=None, max_length=15)
    other_charges: Decimal = Field(default=0, ge=0)
    notes: str | None = None
    lines: list[PurchaseBillLineCreate] = Field(min_length=1)


class PurchaseBillUpdate(BaseModel):
    party_id: UUID | None = Field(default=None)
    bill_date: date | None = None
    due_date: date | None = None
    supplier_invoice_number: str | None = Field(default=None, max_length=100)
    supplier_name_snapshot: str | None = Field(default=None, min_length=1, max_length=250)
    supplier_gstin_snapshot: str | None = None
    other_charges: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    lines: list[PurchaseBillLineCreate] | None = Field(default=None, min_length=1)


class PurchaseBillPost(BaseModel):
    pass


class PurchaseBillCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class PurchaseBillOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    bill_number: str | None
    bill_date: date
    due_date: date | None
    status: Literal["draft", "posted", "cancelled"]
    payment_status: Literal["unpaid", "partially_paid", "paid"]
    supplier_name_snapshot: str
    subtotal: Decimal
    discount_total: Decimal
    taxable_total: Decimal
    cgst_total: Decimal
    sgst_total: Decimal
    igst_total: Decimal
    cess_total: Decimal
    other_charges: Decimal
    grand_total: Decimal
    paid_total: Decimal