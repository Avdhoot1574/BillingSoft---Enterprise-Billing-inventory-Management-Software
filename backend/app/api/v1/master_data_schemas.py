import uuid
from datetime import date
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


# ----------------------------- Units

class UnitCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    abbreviation: str = Field(min_length=1, max_length=20)
    decimal_places: int = Field(default=2, ge=0, le=6)


class UnitUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    abbreviation: str | None = Field(default=None, min_length=1, max_length=20)
    decimal_places: int | None = Field(default=None, ge=0, le=6)


# ----------------------------- Categories

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    parent_id: uuid.UUID | None = None


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    parent_id: uuid.UUID | None = None


# ----------------------------- Tax rates

class TaxRateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    tax_type: Literal["gst", "cess", "other", "exempt", "nil_rated"] = "gst"
    rate_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    cgst_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    sgst_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    igst_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    cess_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool = True

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_from and self.effective_to:
            if self.effective_to < self.effective_from:
                raise ValueError("effective_to cannot be earlier than effective_from")
        return self


class TaxRateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    tax_type: Literal["gst", "cess", "other", "exempt", "nil_rated"] | None = None
    rate_percent: Decimal | None = Field(default=None, ge=0, le=100)
    cgst_percent: Decimal | None = Field(default=None, ge=0, le=100)
    sgst_percent: Decimal | None = Field(default=None, ge=0, le=100)
    igst_percent: Decimal | None = Field(default=None, ge=0, le=100)
    cess_percent: Decimal | None = Field(default=None, ge=0, le=100)
    effective_from: date | None = None
    effective_to: date | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.effective_from and self.effective_to:
            if self.effective_to < self.effective_from:
                raise ValueError("effective_to cannot be earlier than effective_from")
        return self


# ----------------------------- Items

class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    unit_id: uuid.UUID
    category_id: uuid.UUID | None = None
    tax_rate_id: uuid.UUID | None = None
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = None
    kind: Literal["goods", "service"] = "goods"
    hsn_sac: str | None = Field(default=None, max_length=20)
    barcode: str | None = Field(default=None, max_length=100)
    sale_price: Decimal = Field(default=Decimal("0"), ge=0)
    purchase_price: Decimal = Field(default=Decimal("0"), ge=0)
    opening_quantity: Decimal = Decimal("0")
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0)
    sale_price_includes_tax: bool = False
    purchase_price_includes_tax: bool = False
    track_inventory: bool = True


class ItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit_id: uuid.UUID | None = None
    category_id: uuid.UUID | None = None
    tax_rate_id: uuid.UUID | None = None
    sku: str | None = Field(default=None, max_length=100)
    description: str | None = None
    kind: Literal["goods", "service"] | None = None
    hsn_sac: str | None = Field(default=None, max_length=20)
    barcode: str | None = Field(default=None, max_length=100)
    sale_price: Decimal | None = Field(default=None, ge=0)
    purchase_price: Decimal | None = Field(default=None, ge=0)
    opening_quantity: Decimal | None = None
    reorder_level: Decimal | None = Field(default=None, ge=0)
    sale_price_includes_tax: bool | None = None
    purchase_price_includes_tax: bool | None = None
    track_inventory: bool | None = None


# ----------------------------- Unit conversions

class UnitConversionCreate(BaseModel):
    from_unit_id: uuid.UUID
    to_unit_id: uuid.UUID
    factor: Decimal = Field(gt=0, max_digits=20, decimal_places=8)

    @model_validator(mode="after")
    def validate_units(self):
        if self.from_unit_id == self.to_unit_id:
            raise ValueError("from_unit_id and to_unit_id must be different")
        return self


# ----------------------------- Warehouses

class WarehouseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    code: str | None = Field(default=None, max_length=50)
    address: str | None = None
    is_default: bool = False
    is_active: bool = True


class WarehouseUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    code: str | None = Field(default=None, max_length=50)
    address: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None