import re
import secrets
import uuid
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.context import CompanyContext, CurrentUser
from app.core.errors import AppError
from app.core.permissions import ALL, PERMISSIONS, SYSTEM_ROLES
from app.core.security import hash_password, hash_token
from app.modules.audit.service import record_audit

# (document_type, prefix). GST allows at most 16 characters in an invoice number, so keep prefixes short.
DEFAULT_SEQUENCES = [
    ("sales_invoice", "INV-"), ("purchase_bill", "BILL-"), ("payment_in", "RCT-"), ("payment_out", "PAY-"),
    ("journal_entry", "JV-"), ("sales_return", "CN-"), ("purchase_return", "DN-"), ("quotation", "QT-"),
    ("sales_order", "SO-"), ("purchase_order", "PO-"), ("delivery_challan", "DC-"), ("expense", "EXP-"),
]


# ---------------------------------------------------------------- roles & permissions
def sync_permissions(db: Session) -> None:
    for code, description in PERMISSIONS.items():
        db.execute(
            text("INSERT INTO permissions (code, description) VALUES (:c, :d) ON CONFLICT (code) DO NOTHING"),
            {"c": code, "d": description},
        )


def ensure_system_roles(db: Session, tenant_id: uuid.UUID) -> dict[str, uuid.UUID]:
    ids: dict[str, uuid.UUID] = {}
    for name, (description, perms) in SYSTEM_ROLES.items():
        role_id = db.execute(
            text(
                """INSERT INTO roles (tenant_id, name, description, is_system_role)
                   VALUES (:t, :n, :d, true)
                   ON CONFLICT (tenant_id, name) DO UPDATE SET description = EXCLUDED.description
                   RETURNING id"""
            ),
            {"t": tenant_id, "n": name, "d": description},
        ).scalar_one()
        db.execute(
            text(
                """INSERT INTO role_permissions (role_id, permission_id)
                   SELECT :r, p.id FROM permissions p WHERE p.code = ANY(CAST(:codes AS text[]))
                   ON CONFLICT DO NOTHING"""
            ),
            {"r": role_id, "codes": sorted(perms)},
        )
        ids[name] = role_id
    return ids


def load_permissions(db: Session, membership_id: uuid.UUID, is_owner: bool) -> frozenset[str]:
    if is_owner:
        return ALL
    rows = db.execute(
        text(
            """SELECT DISTINCT p.code
               FROM company_member_roles cmr
               JOIN role_permissions rp ON rp.role_id = cmr.role_id
               JOIN permissions p ON p.id = rp.permission_id
               WHERE cmr.company_membership_id = :m"""
        ),
        {"m": membership_id},
    ).scalars().all()
    return frozenset(rows)


# ---------------------------------------------------------------- companies
def _fiscal_year(start_month: int, today: date) -> tuple[date, date, str]:
    y = today.year if today.month >= start_month else today.year - 1
    starts = date(y, start_month, 1)
    ends = date(y + 1, start_month, 1) - timedelta(days=1)
    name = f"FY {y}" if start_month == 1 else f"FY {y}-{str(y + 1)[-2:]}"
    return starts, ends, name


def create_company(db: Session, request: Request, *, user: CurrentUser, data: dict) -> dict:
    """Create tenant (first time), company, settings, owner membership, fiscal period and numbering - atomically."""
    tenant_id = db.execute(
        text(
            """SELECT t.id FROM tenants t
               JOIN tenant_memberships tm ON tm.tenant_id = t.id AND tm.user_id = :u AND tm.status = 'active'
               WHERE t.created_by = :u AND t.status = 'active'
               ORDER BY t.created_at LIMIT 1"""
        ),
        {"u": user.id},
    ).scalar_one_or_none()

    if tenant_id is None:
        slug = re.sub(r"[^a-z0-9]+", "-", data["name"].lower()).strip("-")[:40] or "business"
        slug = f"{slug}-{secrets.token_hex(3)}"
        tenant_id = db.execute(
            text("INSERT INTO tenants (name, slug, created_by) VALUES (:n, :s, :u) RETURNING id"),
            {"n": data["name"], "s": slug, "u": user.id},
        ).scalar_one()
        db.execute(
            text("INSERT INTO tenant_memberships (tenant_id, user_id, status, joined_at) VALUES (:t, :u, 'active', now())"),
            {"t": tenant_id, "u": user.id},
        )

    role_ids = ensure_system_roles(db, tenant_id)

    company = db.execute(
        text(
            """INSERT INTO companies (tenant_id, name, legal_name, gstin, pan, email, phone, address_line1,
                                      address_line2, city, district, state_code, postal_code,
                                      financial_year_start_month)
               VALUES (:tenant_id, :name, :legal_name, :gstin, :pan, :email, :phone, :address_line1,
                       :address_line2, :city, :district, :state_code, :postal_code, :fy_month)
               RETURNING id, tenant_id, name, gstin, state_code, financial_year_start_month, timezone"""
        ),
        {
            "tenant_id": tenant_id,
            "name": data["name"],
            "legal_name": data.get("legal_name"),
            "gstin": data.get("gstin"),
            "pan": data.get("pan"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "address_line1": data.get("address_line1"),
            "address_line2": data.get("address_line2"),
            "city": data.get("city"),
            "district": data.get("district"),
            "state_code": data.get("state_code"),
            "postal_code": data.get("postal_code"),
            "fy_month": data.get("financial_year_start_month", 4),
        },
    ).mappings().one()
    company_id = company["id"]

    db.execute(text("INSERT INTO company_settings (company_id) VALUES (:c)"), {"c": company_id})

    membership_id = db.execute(
        text(
            """INSERT INTO company_memberships (tenant_id, company_id, user_id, status, is_owner)
               VALUES (:t, :c, :u, 'active', true) RETURNING id"""
        ),
        {"t": tenant_id, "c": company_id, "u": user.id},
    ).scalar_one()
    db.execute(
        text("INSERT INTO company_member_roles (company_membership_id, role_id) VALUES (:m, :r)"),
        {"m": membership_id, "r": role_ids["Owner"]},
    )

    today = datetime.now(ZoneInfo(company["timezone"])).date()
    starts, ends, fy_name = _fiscal_year(company["financial_year_start_month"], today)
    period_id = db.execute(
        text(
            """INSERT INTO financial_periods (company_id, name, starts_on, ends_on)
               VALUES (:c, :n, :s, :e) RETURNING id"""
        ),
        {"c": company_id, "n": fy_name, "s": starts, "e": ends},
    ).scalar_one()
    for doc_type, prefix in DEFAULT_SEQUENCES:
        db.execute(
            text(
                """INSERT INTO document_sequences (company_id, document_type, financial_period_id, prefix, padding)
                   VALUES (:c, :d, :p, :prefix, 4)"""
            ),
            {"c": company_id, "d": doc_type, "p": period_id, "prefix": prefix},
        )

    record_audit(
        db, action="company.create", entity_type="company", entity_id=company_id, tenant_id=tenant_id,
        company_id=company_id, actor_user_id=user.id, request=request,
        after={"name": data["name"], "gstin": data.get("gstin"), "financial_period": fy_name},
    )
    db.commit()
    return {k: company[k] for k in ("id", "tenant_id", "name", "gstin", "state_code")} | {"is_owner": True}


def get_company(db: Session, company_id: uuid.UUID) -> dict:
    row = db.execute(
        text(
            """SELECT id, tenant_id, name, legal_name, gstin, pan, email, phone, address_line1, address_line2,
                      city, district, state_code, postal_code, country_code, currency_code,
                      financial_year_start_month, timezone
               FROM companies WHERE id = :c"""
        ),
        {"c": company_id},
    ).mappings().one_or_none()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Company not found")
    return dict(row)


def update_company(db: Session, request: Request, ctx: CompanyContext, data: dict) -> dict:
    """Update fields on the current company. Only provided fields are changed."""
    company = db.execute(
        text("SELECT id, name FROM companies WHERE id = :c"),
        {"c": ctx.company_id},
    ).mappings().one_or_none()
    if not company:
        raise AppError(404, "NOT_FOUND", "Company not found")

    set_fields = []
    params: dict = {"company_id": ctx.company_id}

    def add(field: str, key: str, val):
        if key in data and data[key] is not None:
            set_fields.append(f"{field} = :{key}")
            params[key] = val

    add("name", "name", data.get("name"))
    add("legal_name", "legal_name", data.get("legal_name"))
    add("gstin", "gstin", data.get("gstin"))
    add("pan", "pan", data.get("pan"))
    add("email", "email", data.get("email"))
    add("phone", "phone", data.get("phone"))
    add("address_line1", "address_line1", data.get("address_line1"))
    add("address_line2", "address_line2", data.get("address_line2"))
    add("city", "city", data.get("city"))
    add("district", "district", data.get("district"))
    add("state_code", "state_code", data.get("state_code"))
    add("postal_code", "postal_code", data.get("postal_code"))
    add("financial_year_start_month", "financial_year_start_month", data.get("financial_year_start_month"))

    if not set_fields:
        raise AppError(400, "NO_FIELDS", "No fields to update")

    set_fields.append("updated_at = now()")
    sql = f"""
        UPDATE companies
        SET {', '.join(set_fields)}
        WHERE id = :company_id
    """
    result = db.execute(text(sql), params)
    if result.rowcount == 0:
        raise AppError(404, "NOT_FOUND", "Company not found")

    record_audit(
        db, action="company.update", entity_type="company", entity_id=ctx.company_id,
        tenant_id=ctx.tenant_id, company_id=ctx.company_id, actor_user_id=ctx.user.id, request=request,
        after={k: v for k, v in data.items() if v is not None},
    )
    db.commit()
    return get_company(db, ctx.company_id)


# ---------------------------------------------------------------- members & invitations
def list_roles(db: Session, tenant_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        text("SELECT id, name, description, is_system_role FROM roles WHERE tenant_id = :t ORDER BY name"),
        {"t": tenant_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def list_members(db: Session, company_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        text(
            """SELECT cm.id AS membership_id, cm.user_id, u.email, u.full_name, cm.status, cm.is_owner,
                      COALESCE(array_agg(r.name ORDER BY r.name) FILTER (WHERE r.id IS NOT NULL), '{}') AS roles
               FROM company_memberships cm
               JOIN users u ON u.id = cm.user_id
               LEFT JOIN company_member_roles cmr ON cmr.company_membership_id = cm.id
               LEFT JOIN roles r ON r.id = cmr.role_id
               WHERE cm.company_id = :c
               GROUP BY cm.id, u.id
               ORDER BY u.full_name"""
        ),
        {"c": company_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def _assignable_role(db: Session, tenant_id: uuid.UUID, role_id: uuid.UUID) -> dict:
    role = db.execute(
        text("SELECT id, name FROM roles WHERE id = :r AND tenant_id = :t"), {"r": role_id, "t": tenant_id}
    ).mappings().one_or_none()
    if role is None:
        raise AppError(404, "ROLE_NOT_FOUND", "Role not found")
    if role["name"] == "Owner":
        raise AppError(422, "ROLE_NOT_ASSIGNABLE", "The Owner role cannot be assigned to other users")
    return dict(role)


def invite_member(db: Session, request: Request, ctx: CompanyContext, *, email: str, role_id: uuid.UUID) -> dict:
    email = email.strip().lower()
    role = _assignable_role(db, ctx.tenant_id, role_id)

    already = db.execute(
        text(
            """SELECT 1 FROM company_memberships cm JOIN users u ON u.id = cm.user_id
               WHERE cm.company_id = :c AND cm.status = 'active' AND lower(u.email) = :e"""
        ),
        {"c": ctx.company_id, "e": email},
    ).first()
    if already:
        raise AppError(409, "ALREADY_MEMBER", "This user already has access to the company")

    s = get_settings()
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=s.invitation_valid_days)
    try:
        inv_id = db.execute(
            text(
                """INSERT INTO invitations (tenant_id, company_id, email, role_id, token_hash, invited_by, expires_at)
                   VALUES (:t, :c, :e, :r, :h, :u, :x) RETURNING id"""
            ),
            {"t": ctx.tenant_id, "c": ctx.company_id, "e": email, "r": role_id, "h": hash_token(token),
             "u": ctx.user.id, "x": expires_at},
        ).scalar_one()
    except IntegrityError:
        db.rollback()
        raise AppError(409, "INVITATION_PENDING", "A pending invitation already exists for this email")

    record_audit(db, action="member.invite", entity_type="invitation", entity_id=inv_id, tenant_id=ctx.tenant_id,
                 company_id=ctx.company_id, actor_user_id=ctx.user.id, request=request,
                 after={"email": email, "role": role["name"]})
    db.commit()
    # Until the email outbox exists the token is only returned in dev/test.
    return {"id": inv_id, "email": email, "role": role["name"], "expires_at": expires_at,
            "token": token if s.expose_invitation_tokens else None}


def add_member(db: Session, request: Request, ctx: CompanyContext, *, name: str, email: str,
               password: str, role_id: uuid.UUID) -> dict:
    """Owner directly creates a user account and adds them to this company with a role."""
    email = email.strip().lower()
    name = name.strip()

    role = _assignable_role(db, ctx.tenant_id, role_id)

    # Check if user already exists
    user_row = db.execute(
        text("SELECT id, full_name FROM users WHERE lower(email) = :email"),
        {"email": email},
    ).mappings().one_or_none()

    if user_row is None:
        user_id = db.execute(
            text("""INSERT INTO users (email, full_name, password_hash, is_active)
                    VALUES (:email, :name, :hash, true) RETURNING id"""),
            {"email": email, "name": name, "hash": hash_password(password)},
        ).scalar_one()
    else:
        user_id = user_row["id"]

    # Check if already an active member of this company
    already = db.execute(
        text("""SELECT 1 FROM company_memberships
                WHERE company_id = :c AND user_id = :u AND status = 'active'"""),
        {"c": ctx.company_id, "u": user_id},
    ).first()
    if already:
        raise AppError(409, "ALREADY_MEMBER", "This user is already a member of this company")

    # Ensure tenant membership exists
    db.execute(
        text("""INSERT INTO tenant_memberships (tenant_id, user_id, status, joined_at)
                VALUES (:t, :u, 'active', now())
                ON CONFLICT (tenant_id, user_id) DO UPDATE SET status = 'active'"""),
        {"t": ctx.tenant_id, "u": user_id},
    )

    # Create company membership
    membership_id = db.execute(
        text("""INSERT INTO company_memberships (tenant_id, company_id, user_id, status, is_owner)
                VALUES (:t, :c, :u, 'active', false) RETURNING id"""),
        {"t": ctx.tenant_id, "c": ctx.company_id, "u": user_id},
    ).scalar_one()

    # Assign role
    db.execute(
        text("INSERT INTO company_member_roles (company_membership_id, role_id) VALUES (:m, :r)"),
        {"m": membership_id, "r": role_id},
    )

    record_audit(
        db, action="member.added", entity_type="company_membership", entity_id=membership_id,
        tenant_id=ctx.tenant_id, company_id=ctx.company_id, actor_user_id=ctx.user.id, request=request,
        after={"email": email, "name": name, "role": role["name"]},
    )
    db.commit()

    return {
        "membership_id": membership_id,
        "user_id": user_id,
        "email": email,
        "full_name": name,
        "status": "active",
        "is_owner": False,
        "roles": [role["name"]],
    }


def accept_invitation(db: Session, request: Request, *, user: CurrentUser, token: str) -> dict:
    inv = db.execute(
        text(
            """SELECT i.id, i.tenant_id, i.company_id, i.email, i.role_id, i.status, i.expires_at
               FROM invitations i WHERE i.token_hash = :h FOR UPDATE"""
        ),
        {"h": hash_token(token)},
    ).mappings().one_or_none()
    if inv is None:
        raise AppError(404, "INVITATION_NOT_FOUND", "Invitation not found")
    if inv["status"] != "pending":
        raise AppError(409, "INVITATION_NOT_PENDING", "This invitation is no longer valid")
    if inv["expires_at"] <= datetime.now(timezone.utc):
        db.execute(text("UPDATE invitations SET status = 'expired' WHERE id = :i"), {"i": inv["id"]})
        db.commit()
        raise AppError(410, "INVITATION_EXPIRED", "This invitation has expired")
    if inv["email"].lower() != user.email.lower():
        raise AppError(403, "INVITATION_EMAIL_MISMATCH", "This invitation was issued to a different email address")

    db.execute(
        text(
            """INSERT INTO tenant_memberships (tenant_id, user_id, status, joined_at)
               VALUES (:t, :u, 'active', now())
               ON CONFLICT (tenant_id, user_id) DO UPDATE SET status = 'active'"""
        ),
        {"t": inv["tenant_id"], "u": user.id},
    )
    membership_id = db.execute(
        text(
            """INSERT INTO company_memberships (tenant_id, company_id, user_id, status, is_owner)
               VALUES (:t, :c, :u, 'active', false)
               ON CONFLICT (company_id, user_id) DO UPDATE SET status = 'active'
               RETURNING id"""
        ),
        {"t": inv["tenant_id"], "c": inv["company_id"], "u": user.id},
    ).scalar_one()
    db.execute(text("DELETE FROM company_member_roles WHERE company_membership_id = :m"), {"m": membership_id})
    db.execute(text("INSERT INTO company_member_roles (company_membership_id, role_id) VALUES (:m, :r)"),
               {"m": membership_id, "r": inv["role_id"]})
    db.execute(
        text("UPDATE invitations SET status = 'accepted', accepted_by = :u, accepted_at = now() WHERE id = :i"),
        {"u": user.id, "i": inv["id"]},
    )
    record_audit(db, action="member.accept_invitation", entity_type="company_membership", entity_id=membership_id,
                 tenant_id=inv["tenant_id"], company_id=inv["company_id"], actor_user_id=user.id, request=request)
    db.commit()
    return {"company_id": inv["company_id"], "membership_id": membership_id}


def _scoped_membership(db: Session, company_id: uuid.UUID, membership_id: uuid.UUID) -> dict:
    """Always scoped by company_id so a membership id from another company is simply 'not found'."""
    row = db.execute(
        text("SELECT id, user_id, is_owner, status FROM company_memberships WHERE id = :m AND company_id = :c"),
        {"m": membership_id, "c": company_id},
    ).mappings().one_or_none()
    if row is None:
        raise AppError(404, "NOT_FOUND", "Member not found")
    return dict(row)


def change_member_role(db: Session, request: Request, ctx: CompanyContext, *, membership_id: uuid.UUID,
                       role_id: uuid.UUID) -> None:
    member = _scoped_membership(db, ctx.company_id, membership_id)
    if member["is_owner"]:
        raise AppError(409, "OWNER_ROLE_LOCKED", "The owner's role cannot be changed")
    role = _assignable_role(db, ctx.tenant_id, role_id)
    before = db.execute(
        text("""SELECT r.name FROM company_member_roles cmr JOIN roles r ON r.id = cmr.role_id
                WHERE cmr.company_membership_id = :m"""),
        {"m": membership_id},
    ).scalars().all()
    db.execute(text("DELETE FROM company_member_roles WHERE company_membership_id = :m"), {"m": membership_id})
    db.execute(text("INSERT INTO company_member_roles (company_membership_id, role_id) VALUES (:m, :r)"),
               {"m": membership_id, "r": role_id})
    record_audit(db, action="member.change_role", entity_type="company_membership", entity_id=membership_id,
                 tenant_id=ctx.tenant_id, company_id=ctx.company_id, actor_user_id=ctx.user.id, request=request,
                 before={"roles": list(before)}, after={"roles": [role["name"]]})
    db.commit()


def remove_member(db: Session, request: Request, ctx: CompanyContext, *, membership_id: uuid.UUID) -> None:
    member = _scoped_membership(db, ctx.company_id, membership_id)
    if member["is_owner"]:
        raise AppError(409, "OWNER_CANNOT_BE_REMOVED", "The company owner cannot be removed")
    if member["user_id"] == ctx.user.id:
        raise AppError(409, "CANNOT_REMOVE_SELF", "You cannot remove your own access")
    db.execute(text("UPDATE company_memberships SET status = 'removed' WHERE id = :m"), {"m": membership_id})
    record_audit(db, action="member.remove", entity_type="company_membership", entity_id=membership_id,
                 tenant_id=ctx.tenant_id, company_id=ctx.company_id, actor_user_id=ctx.user.id, request=request,
                 before={"status": member["status"]}, after={"status": "removed"})
    db.commit()
