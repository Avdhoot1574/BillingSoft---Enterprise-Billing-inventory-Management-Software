
import re
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

PartyKind = Literal["customer", "supplier", "both"]
TaxRegistrationType = Literal[
    "regular", "composition", "unregistered", "consumer", "overseas", "other"
]
BalanceSide = Literal["receivable", "payable", "none"]
AddressType = Literal["billing", "shipping", "other"]

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
PHONE_RE = re.compile(r"^\+?[0-9]{8,15}$")


class PartyAddressIn(BaseModel):
    address_type: AddressType
    line1: str = Field(min_length=1, max_length=250)
    line2: str | None = Field(default=None, max_length=250)
    city: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    state_code: str | None = Field(default=None, pattern=r"^[0-9]{2}$")
    state_name: str | None = Field(default=None, max_length=100)
    postal_code: str | None = Field(default=None, max_length=20)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    is_default: bool = False

    @field_validator("line1", "line2", "city", "district", "state_name", "postal_code")
    @classmethod
    def trim_address_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("country_code")
    @classmethod
    def normalize_country(cls, value: str) -> str:
        return value.strip().upper()


class PartyAddressOut(PartyAddressIn):
    id: uuid.UUID
    created_at: datetime


class PartyCreateIn(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    kind: PartyKind
    gstin: str | None = Field(default=None, max_length=15)
    pan: str | None = Field(default=None, max_length=10)
    tax_registration_type: TaxRegistrationType = "unregistered"
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    alternate_phone: str | None = Field(default=None, max_length=30)
    opening_balance: Decimal = Field(default=Decimal("0"), max_digits=19, decimal_places=4)
    opening_balance_side: BalanceSide | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0, max_digits=19, decimal_places=4)
    payment_terms_days: int = Field(default=0, ge=0, le=3650)
    notes: str | None = Field(default=None, max_length=5000)
    addresses: list[PartyAddressIn] = Field(default_factory=list, max_length=20)

    @field_validator("code", "name", "legal_name", "phone", "alternate_phone", "notes")
    @classmethod
    def trim_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("gstin")
    @classmethod
    def normalize_gstin(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip().upper()
        if not GSTIN_RE.fullmatch(value):
            raise ValueError("GSTIN format is invalid")
        return value

    @field_validator("pan")
    @classmethod
    def normalize_pan(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip().upper()
        if not PAN_RE.fullmatch(value):
            raise ValueError("PAN format is invalid")
        return value

    @field_validator("phone", "alternate_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = re.sub(r"\s+", "", value)
        if not PHONE_RE.fullmatch(value):
            raise ValueError("Phone must contain 8-15 digits, optionally starting with +")
        return value

    @model_validator(mode="after")
    def validate_balance(self):
        if self.opening_balance != 0 and self.opening_balance_side in (None, "none"):
            raise ValueError("opening_balance_side must be receivable or payable for a non-zero balance")
        if self.opening_balance == 0 and self.opening_balance_side is None:
            self.opening_balance_side = "none"
        return self


class PartyUpdateIn(BaseModel):
    code: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    kind: PartyKind | None = None
    gstin: str | None = Field(default=None, max_length=15)
    pan: str | None = Field(default=None, max_length=10)
    tax_registration_type: TaxRegistrationType | None = None
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    alternate_phone: str | None = Field(default=None, max_length=30)
    opening_balance: Decimal | None = Field(default=None, max_digits=19, decimal_places=4)
    opening_balance_side: BalanceSide | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0, max_digits=19, decimal_places=4)
    payment_terms_days: int | None = Field(default=None, ge=0, le=3650)
    notes: str | None = Field(default=None, max_length=5000)
    addresses: list[PartyAddressIn] | None = Field(default=None, max_length=20)

    @field_validator("code", "name", "legal_name", "phone", "alternate_phone", "notes")
    @classmethod
    def trim_text(cls, value):
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("gstin")
    @classmethod
    def normalize_gstin(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip().upper()
        if not GSTIN_RE.fullmatch(value):
            raise ValueError("GSTIN format is invalid")
        return value

    @field_validator("pan")
    @classmethod
    def normalize_pan(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = value.strip().upper()
        if not PAN_RE.fullmatch(value):
            raise ValueError("PAN format is invalid")
        return value

    @field_validator("phone", "alternate_phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if not value:
            return None
        value = re.sub(r"\s+", "", value)
        if not PHONE_RE.fullmatch(value):
            raise ValueError("Phone must contain 8-15 digits, optionally starting with +")
        return value


class PartyOut(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    code: str | None = None
    name: str
    legal_name: str | None = None
    kind: PartyKind
    gstin: str | None = None
    pan: str | None = None
    tax_registration_type: TaxRegistrationType
    email: str | None = None
    phone: str | None = None
    alternate_phone: str | None = None
    opening_balance: Decimal
    opening_balance_side: BalanceSide | None = None
    credit_limit: Decimal | None = None
    payment_terms_days: int
    notes: str | None = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    addresses: list[PartyAddressOut] = Field(default_factory=list)
