
import uuid

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import CompanyContext
from app.core.errors import AppError
from app.modules.audit.service import record_audit


def _party_or_404(db: Session, company_id: uuid.UUID, party_id: uuid.UUID) -> dict:
    row = db.execute(
        text("""
            SELECT *
            FROM parties
            WHERE id = :party_id
              AND company_id = :company_id
        """),
        {"party_id": party_id, "company_id": company_id},
    ).mappings().one_or_none()

    if row is None:
        raise AppError(404, "PARTY_NOT_FOUND", "Party was not found")
    return dict(row)


def _addresses(db: Session, company_id: uuid.UUID, party_id: uuid.UUID) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT id, address_type, line1, line2, city, district,
                   state_code, state_name, postal_code, country_code,
                   is_default, created_at
            FROM party_addresses
            WHERE company_id = :company_id
              AND party_id = :party_id
            ORDER BY is_default DESC, address_type, created_at
        """),
        {"company_id": company_id, "party_id": party_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def _party_detail(db: Session, company_id: uuid.UUID, party_id: uuid.UUID) -> dict:
    party = _party_or_404(db, company_id, party_id)
    party["addresses"] = _addresses(db, company_id, party_id)
    return party


def _record_snapshot(party: dict) -> dict:
    keys = (
        "id", "code", "name", "legal_name", "kind", "gstin", "pan",
        "tax_registration_type", "email", "phone", "alternate_phone",
        "opening_balance", "opening_balance_side", "credit_limit",
        "payment_terms_days", "notes", "is_archived",
    )
    return {key: party.get(key) for key in keys}


def _save_addresses(
    db: Session,
    *,
    company_id: uuid.UUID,
    party_id: uuid.UUID,
    addresses: list[dict],
) -> None:
    # Keep at most one default address per address type.
    seen_defaults: set[str] = set()
    for address in addresses:
        if address.get("is_default"):
            address_type = address["address_type"]
            if address_type in seen_defaults:
                raise AppError(
                    422,
                    "DUPLICATE_DEFAULT_ADDRESS",
                    f"Only one default {address_type} address is allowed",
                )
            seen_defaults.add(address_type)

    for address in addresses:
        db.execute(
            text("""
                INSERT INTO party_addresses (
                    company_id, party_id, address_type, line1, line2,
                    city, district, state_code, state_name, postal_code,
                    country_code, is_default
                )
                VALUES (
                    :company_id, :party_id, :address_type, :line1, :line2,
                    :city, :district, :state_code, :state_name, :postal_code,
                    :country_code, :is_default
                )
            """),
            {
                "company_id": company_id,
                "party_id": party_id,
                **address,
            },
        )


def _raise_integrity_error(exc: IntegrityError) -> None:
    message = str(getattr(exc, "orig", exc))
    if "parties_company_id_code_key" in message or "uq_parties_company_code" in message:
        raise AppError(
            409, "PARTY_CODE_EXISTS",
            "A party with this code already exists in this company",
        ) from exc
    raise AppError(
        409, "PARTY_CONFLICT",
        "The party could not be saved because it conflicts with existing data",
    ) from exc


def list_parties(
    db: Session,
    ctx: CompanyContext,
    *,
    search: str | None,
    kind: str | None,
    include_archived: bool,
    limit: int,
    offset: int,
) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT p.*
            FROM parties p
            WHERE p.company_id = :company_id
              AND (:include_archived OR p.is_archived = FALSE)
              AND (CAST(:kind AS text) IS NULL OR p.kind::text = :kind)
              AND (
                    CAST(:search AS text) IS NULL
                    OR p.name ILIKE '%' || :search || '%'
                    OR COALESCE(p.code, '') ILIKE '%' || :search || '%'
                    OR COALESCE(p.phone, '') ILIKE '%' || :search || '%'
                    OR COALESCE(p.email, '') ILIKE '%' || :search || '%'
                    OR COALESCE(p.gstin, '') ILIKE '%' || :search || '%'
              )
            ORDER BY lower(p.name), p.id
            LIMIT :limit OFFSET :offset
        """),
        {
            "company_id": ctx.company_id,
            "include_archived": include_archived,
            "kind": kind,
            "search": search.strip() if search and search.strip() else None,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()

    results = []
    for row in rows:
        party = dict(row)
        party["addresses"] = _addresses(db, ctx.company_id, party["id"])
        results.append(party)
    return results


def get_party(db: Session, ctx: CompanyContext, party_id: uuid.UUID) -> dict:
    return _party_detail(db, ctx.company_id, party_id)


def create_party(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    data: dict,
) -> dict:
    addresses = data.pop("addresses", [])

    try:
        row = db.execute(
            text("""
                INSERT INTO parties (
                    company_id, code, name, legal_name, kind, gstin, pan,
                    tax_registration_type, email, phone, alternate_phone,
                    opening_balance, opening_balance_side, credit_limit,
                    payment_terms_days, notes
                )
                VALUES (
                    :company_id, :code, :name, :legal_name,
                    CAST(:kind AS party_kind), :gstin, :pan,
                    CAST(:tax_registration_type AS tax_registration_type),
                    :email, :phone, :alternate_phone, :opening_balance,
                    :opening_balance_side, :credit_limit, :payment_terms_days, :notes
                )
                RETURNING *
            """),
            {"company_id": ctx.company_id, **data},
        ).mappings().one()

        party = dict(row)
        _save_addresses(
            db,
            company_id=ctx.company_id,
            party_id=party["id"],
            addresses=addresses,
        )

        record_audit(
            db,
            action="party.created",
            entity_type="party",
            entity_id=party["id"],
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after=_record_snapshot(party),
        )
        db.commit()
        return _party_detail(db, ctx.company_id, party["id"])

    except IntegrityError as exc:
        db.rollback()
        _raise_integrity_error(exc)
    except Exception:
        db.rollback()
        raise


def update_party(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    party_id: uuid.UUID,
    data: dict,
) -> dict:
    addresses = data.pop("addresses", None)

    try:
        current = _party_or_404(db, ctx.company_id, party_id)
        if current["is_archived"]:
            raise AppError(409, "PARTY_ARCHIVED", "Archived parties cannot be edited")

        changes = {key: value for key, value in data.items() if key != "id"}
        if not changes and addresses is None:
            raise AppError(400, "NO_CHANGES", "No changes were provided")

        if changes:
            allowed_columns = {
                "code", "name", "legal_name", "kind", "gstin", "pan",
                "tax_registration_type", "email", "phone", "alternate_phone",
                "opening_balance", "opening_balance_side", "credit_limit",
                "payment_terms_days", "notes",
            }
            if not set(changes).issubset(allowed_columns):
                raise AppError(400, "INVALID_FIELDS", "One or more fields cannot be updated")

            assignments = []
            for key in changes:
                if key == "kind":
                    assignments.append(f"{key} = CAST(:{key} AS party_kind)")
                elif key == "tax_registration_type":
                    assignments.append(f"{key} = CAST(:{key} AS tax_registration_type)")
                else:
                    assignments.append(f"{key} = :{key}")

            assignments.append("updated_at = now()")
            db.execute(
                text(f"""
                    UPDATE parties
                    SET {", ".join(assignments)}
                    WHERE id = :party_id
                      AND company_id = :company_id
                """),
                {**changes, "party_id": party_id, "company_id": ctx.company_id},
            )

        if addresses is not None:
            db.execute(
                text("""
                    DELETE FROM party_addresses
                    WHERE company_id = :company_id AND party_id = :party_id
                """),
                {"company_id": ctx.company_id, "party_id": party_id},
            )
            _save_addresses(
                db,
                company_id=ctx.company_id,
                party_id=party_id,
                addresses=addresses,
            )

        updated = _party_or_404(db, ctx.company_id, party_id)
        record_audit(
            db,
            action="party.updated",
            entity_type="party",
            entity_id=party_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            before=_record_snapshot(current),
            after=_record_snapshot(updated),
        )
        db.commit()
        return _party_detail(db, ctx.company_id, party_id)

    except IntegrityError as exc:
        db.rollback()
        _raise_integrity_error(exc)
    except Exception:
        db.rollback()
        raise


def archive_party(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    party_id: uuid.UUID,
) -> dict:
    try:
        current = _party_or_404(db, ctx.company_id, party_id)
        if current["is_archived"]:
            return _party_detail(db, ctx.company_id, party_id)

        db.execute(
            text("""
                UPDATE parties
                SET is_archived = TRUE, updated_at = now()
                WHERE id = :party_id AND company_id = :company_id
            """),
            {"party_id": party_id, "company_id": ctx.company_id},
        )
        updated = _party_or_404(db, ctx.company_id, party_id)

        record_audit(
            db,
            action="party.archived",
            entity_type="party",
            entity_id=party_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            before=_record_snapshot(current),
            after=_record_snapshot(updated),
        )
        db.commit()
        return _party_detail(db, ctx.company_id, party_id)

    except Exception:
        db.rollback()
        raise
