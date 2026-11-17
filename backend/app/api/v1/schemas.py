import re
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
PHONE_RE = re.compile(r"^\+?[0-9]{8,15}$")


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=200)
    phone: str | None = None

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        v = v.replace(" ", "")
        if not PHONE_RE.match(v):
            raise ValueError("phone must be 8-15 digits, optionally starting with +")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10, max_length=500)


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    phone: str | None = None


class CompanyBrief(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    gstin: str | None = None
    state_code: str | None = None
    is_owner: bool


class MeOut(BaseModel):
    user: UserOut
    companies: list[CompanyBrief]


class CompanyCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    gstin: str | None = None
    pan: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    district: str | None = None
    state_code: str | None = Field(default=None, pattern=r"^[0-9]{2}$")
    postal_code: str | None = None
    financial_year_start_month: int = Field(default=4, ge=1, le=12)

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip().upper()
        if not GSTIN_RE.match(v):
            raise ValueError("GSTIN format is invalid")  # format only; checksum validation is a later step
        return v

    @field_validator("pan")
    @classmethod
    def _pan(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip().upper()
        if not PAN_RE.match(v):
            raise ValueError("PAN format is invalid")
        return v

    @model_validator(mode="after")
    def _state_matches_gstin(self) -> "CompanyCreateIn":
        if self.gstin:
            if self.state_code and self.state_code != self.gstin[:2]:
                raise ValueError("state_code does not match the first two digits of the GSTIN")
            self.state_code = self.gstin[:2]
        return self


class CompanyUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    gstin: str | None = None
    pan: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    district: str | None = None
    state_code: str | None = Field(default=None, pattern=r"^[0-9]{2}$")
    postal_code: str | None = None
    financial_year_start_month: int | None = Field(default=None, ge=1, le=12)

    @field_validator("gstin")
    @classmethod
    def _gstin(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip().upper()
        if not GSTIN_RE.match(v):
            raise ValueError("GSTIN format is invalid")
        return v

    @field_validator("pan")
    @classmethod
    def _pan(cls, v: str | None) -> str | None:
        if not v:
            return None
        v = v.strip().upper()
        if not PAN_RE.match(v):
            raise ValueError("PAN format is invalid")
        return v

    @model_validator(mode="after")
    def _state_matches_gstin(self) -> "CompanyUpdateIn":
        if self.gstin:
            if self.state_code and self.state_code != self.gstin[:2]:
                raise ValueError("state_code does not match the first two digits of the GSTIN")
            self.state_code = self.gstin[:2]
        return self


class CompanyDetailOut(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    legal_name: str | None = None
    gstin: str | None = None
    pan: str | None = None
    email: str | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    district: str | None = None
    state_code: str | None = None
    postal_code: str | None = None
    country_code: str
    currency_code: str
    financial_year_start_month: int
    timezone: str
    is_owner: bool
    permissions: list[str]


class RoleOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None = None
    is_system_role: bool


class MemberOut(BaseModel):
    membership_id: uuid.UUID
    user_id: uuid.UUID
    email: str
    full_name: str
    status: str
    is_owner: bool
    roles: list[str]


class InviteIn(BaseModel):
    email: EmailStr
    role_id: uuid.UUID


class MemberAddIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    role_id: uuid.UUID


class InviteOut(BaseModel):
    id: uuid.UUID
    email: str
    role: str
    expires_at: datetime
    token: str | None = None  # only populated when EXPOSE_INVITATION_TOKENS=true (dev/test)


class AcceptInviteIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class AcceptInviteOut(BaseModel):
    company_id: uuid.UUID
    membership_id: uuid.UUID


class RoleChangeIn(BaseModel):
    role_id: uuid.UUID


class AuditEventOut(BaseModel):
    id: uuid.UUID
    action: str
    entity_type: str
    entity_id: uuid.UUID | None = None
    actor_user_id: uuid.UUID | None = None
    actor_email: str | None = None
    request_id: str | None = None
    before_data: dict[str, Any] | None = None
    after_data: dict[str, Any] | None = None
    created_at: datetime
