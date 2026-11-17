from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InvoiceLineCreate(BaseModel):
    id: UUID | None = None
    item_id: UUID | None = None
    item_name: str = Field(min_length=1, max_length=250)
    sku: str | None = None
    hsn_sac: str | None = None
    unit_name: str = Field(min_length=1, max_length=50)
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    discount_percent: Decimal = Field(default=0, ge=0, le=100)
    tax_rate_percent: Decimal = Field(default=0, ge=0, le=100)
    warehouse_id: UUID | None = None


class InvoiceCreate(BaseModel):
    party_id: UUID | None = None
    invoice_date: date
    due_date: date | None = None
    place_of_supply_state_code: str | None = Field(default=None, max_length=2)
    supply_type: str = "intra_state"
    customer_name: str = Field(min_length=1, max_length=250)
    customer_gstin: str | None = None
    billing_address: dict = Field(default_factory=dict)
    shipping_address: dict = Field(default_factory=dict)
    other_charges: Decimal = Field(default=0, ge=0)
    notes: str | None = None
    terms: str | None = None
    lines: list[InvoiceLineCreate] = Field(min_length=1)


class InvoiceUpdate(BaseModel):
    party_id: UUID | None = Field(default=None)
    invoice_date: date | None = None
    due_date: date | None = None
    place_of_supply_state_code: str | None = Field(default=None, max_length=2)
    supply_type: str | None = Field(default=None, min_length=1, max_length=20)
    customer_name: str | None = Field(default=None, min_length=1, max_length=250)
    customer_gstin: str | None = None
    billing_address: dict | None = None
    shipping_address: dict | None = None
    other_charges: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None
    terms: str | None = None
    lines: list[InvoiceLineCreate] | None = Field(default=None, min_length=1)


class InvoicePost(BaseModel):
    pass


class InvoiceCancel(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class InvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_number: str | None
    invoice_date: date
    due_date: date | None
    status: Literal["draft", "posted", "cancelled"]
    payment_status: Literal["unpaid", "partially_paid", "paid"]
    customer_name_snapshot: str
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