from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class InvoiceInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid", allow_inf_nan=False)


class InvoiceLineCreate(InvoiceInput):
    id: UUID | None = None
    item_id: UUID | None = None
    item_name: str = Field(min_length=1, max_length=250)
    sku: str | None = None
    hsn_sac: str | None = None
    unit_name: str = Field(min_length=1, max_length=50)
    quantity: Decimal = Field(gt=0, max_digits=20, decimal_places=6)
    unit_price: Decimal = Field(ge=0, max_digits=19, decimal_places=4)
    discount_percent: Decimal = Field(default=0, ge=0, le=100, decimal_places=4)
    tax_rate_percent: Decimal = Field(default=0, ge=0, le=100, decimal_places=4)
    warehouse_id: UUID | None = None


class InvoiceCreate(InvoiceInput):
    party_id: UUID | None = None
    invoice_date: date
    due_date: date | None = None
    place_of_supply_state_code: str | None = Field(default=None, max_length=2)
    supply_type: Literal["intra_state", "inter_state", "export", "other"] = "intra_state"
    customer_name: str = Field(min_length=1, max_length=250)
    customer_gstin: str | None = None
    billing_address: dict = Field(default_factory=dict)
    shipping_address: dict = Field(default_factory=dict)
    other_charges: Decimal = Field(default=0, ge=0, max_digits=17, decimal_places=2)
    notes: str | None = None
    terms: str | None = None
    paid_amount: Decimal = Field(default=0, ge=0, max_digits=17, decimal_places=2)
    lines: list[InvoiceLineCreate] = Field(min_length=1)


class InvoiceUpdate(InvoiceInput):
    party_id: UUID | None = Field(default=None)
    invoice_date: date | None = None
    due_date: date | None = None
    place_of_supply_state_code: str | None = Field(default=None, max_length=2)
    supply_type: Literal["intra_state", "inter_state", "export", "other"] | None = None
    customer_name: str | None = Field(default=None, min_length=1, max_length=250)
    customer_gstin: str | None = None
    billing_address: dict | None = None
    shipping_address: dict | None = None
    other_charges: Decimal | None = Field(default=None, ge=0, max_digits=17, decimal_places=2)
    notes: str | None = None
    terms: str | None = None
    paid_amount: Decimal | None = Field(default=None, ge=0, max_digits=17, decimal_places=2)
    lines: list[InvoiceLineCreate] | None = Field(default=None, min_length=1)


    @model_validator(mode="after")
    def validate_patch(self):
        required = {"invoice_date", "supply_type", "customer_name", "billing_address",
                    "shipping_address", "other_charges", "paid_amount", "lines"}
        for field in required & self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class InvoicePost(BaseModel):
    pass


class InvoicePaymentUpdate(InvoiceInput):
    paid_amount: Decimal = Field(ge=0, max_digits=17, decimal_places=2)


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

class InvoiceDetailOut(InvoiceOut):
    party_id: UUID | None
    supply_type: str
    place_of_supply_state_code: str | None
    customer_gstin_snapshot: str | None
    billing_address_snapshot: dict
    shipping_address_snapshot: dict
    notes: str | None
    terms: str | None
    version: int
    lines: list[dict] = Field(default_factory=list)
