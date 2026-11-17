import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.context import CompanyContext
from app.core.errors import AppError
from app.modules.audit.service import record_audit


# Only these predefined tables and columns can be used in dynamic SQL.
CONFIG = {
    "units": {
        "table": "units",
        "fields": {"name", "abbreviation", "decimal_places"},
        "order": "name",
    },
    "categories": {
        "table": "item_categories",
        "fields": {"name", "parent_id"},
        "order": "name",
    },
    "tax_rates": {
        "table": "tax_rates",
        "fields": {
            "name", "tax_type", "rate_percent", "cgst_percent",
            "sgst_percent", "igst_percent", "cess_percent",
            "effective_from", "effective_to", "is_active",
        },
        "order": "name",
    },
    "items": {
        "table": "items",
        "fields": {
            "category_id", "unit_id", "tax_rate_id", "sku", "name",
            "description", "kind", "hsn_sac", "barcode", "sale_price",
            "purchase_price", "opening_quantity", "reorder_level",
            "sale_price_includes_tax", "purchase_price_includes_tax",
            "track_inventory",
        },
        "order": "name",
    },
    "warehouses": {
        "table": "warehouses",
        "fields": {"name", "code", "address", "is_default", "is_active"},
        "order": "name",
    },
}

ENTITY_NAMES = {
    "units": "unit",
    "categories": "item_category",
    "tax_rates": "tax_rate",
    "items": "item",
    "warehouses": "warehouse",
}


def _config(resource: str) -> dict:
    if resource not in CONFIG:
        raise AppError(400, "INVALID_RESOURCE", "Unsupported master-data resource")
    return CONFIG[resource]


def _clean_values(resource: str, data: dict[str, Any]) -> dict[str, Any]:
    allowed = _config(resource)["fields"]
    values = {key: value for key, value in data.items() if key in allowed}

    if not values:
        raise AppError(400, "EMPTY_UPDATE", "At least one field must be provided")

    # Normalize blank optional strings to NULL.
    for key in ("sku", "barcode", "code"):
        if key in values and isinstance(values[key], str):
            values[key] = values[key].strip() or None

    for key in ("name", "abbreviation"):
        if key in values and isinstance(values[key], str):
            values[key] = values[key].strip()
            if not values[key]:
                raise AppError(422, "INVALID_FIELD", f"{key} cannot be blank")

    return values


def _get_one(db: Session, ctx: CompanyContext, resource: str, record_id: uuid.UUID) -> dict:
    cfg = _config(resource)
    row = db.execute(
        text(
            f"SELECT * FROM {cfg['table']} "
            "WHERE company_id = :company_id AND id = :id"
        ),
        {"company_id": ctx.company_id, "id": record_id},
    ).mappings().one_or_none()

    if row is None:
        raise AppError(404, "RECORD_NOT_FOUND", "Record not found")
    return dict(row)


def list_records(
    db: Session,
    ctx: CompanyContext,
    resource: str,
    *,
    search: str | None = None,
    include_inactive: bool = False,
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    cfg = _config(resource)
    conditions = ["company_id = :company_id"]
    params: dict[str, Any] = {
        "company_id": ctx.company_id,
        "limit": limit,
        "offset": offset,
    }

    if resource == "items":
        conditions.append("is_archived = false")
    elif resource in {"tax_rates", "warehouses"} and not include_inactive:
        conditions.append("is_active = true")

    if search and resource in {"units", "categories", "tax_rates", "items", "warehouses"}:
        conditions.append("name ILIKE :search")
        params["search"] = f"%{search.strip()}%"

    query = (
        f"SELECT * FROM {cfg['table']} WHERE {' AND '.join(conditions)} "
        f"ORDER BY {cfg['order']} LIMIT :limit OFFSET :offset"
    )
    rows = db.execute(text(query), params).mappings().all()
    return [dict(row) for row in rows]


def create_record(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    resource: str,
    data: dict[str, Any],
) -> dict:
    cfg = _config(resource)
    values = _clean_values(resource, data)

    # kind is a PostgreSQL enum in the baseline schema.
    columns = ["company_id", *values.keys()]
    placeholders = [":company_id", *[f":{key}" for key in values]]

    if resource == "items" and "kind" in values:
        placeholders[columns.index("kind")] = "CAST(:kind AS item_kind)"

    params = {"company_id": ctx.company_id, **values}
    columns_sql = ", ".join(columns)
    values_sql = ", ".join(placeholders)

    try:
        row = db.execute(
            text(
                f"INSERT INTO {cfg['table']} ({columns_sql}) "
                f"VALUES ({values_sql}) RETURNING *"
            ),
            params,
        ).mappings().one()

        result = dict(row)
        record_audit(
            db,
            action=f"{resource}.create",
            entity_type=ENTITY_NAMES[resource],
            entity_id=result["id"],
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after=result,
        )
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "MASTER_DATA_CONFLICT",
            "The record conflicts with existing data or references an invalid record in this company.",
        ) from exc


def update_record(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    resource: str,
    record_id: uuid.UUID,
    data: dict[str, Any],
) -> dict:
    cfg = _config(resource)
    before = _get_one(db, ctx, resource, record_id)
    values = _clean_values(resource, data)

    if resource == "items" and "kind" in values:
        assignments = [
            f"{key} = CAST(:{key} AS item_kind)" if key == "kind" else f"{key} = :{key}"
            for key in values
        ]
    else:
        assignments = [f"{key} = :{key}" for key in values]

    if resource == "items":
        assignments.append("updated_at = now()")

    params = {"company_id": ctx.company_id, "id": record_id, **values}

    try:
        row = db.execute(
            text(
                f"UPDATE {cfg['table']} SET {', '.join(assignments)} "
                "WHERE company_id = :company_id AND id = :id RETURNING *"
            ),
            params,
        ).mappings().one()

        result = dict(row)
        record_audit(
            db,
            action=f"{resource}.update",
            entity_type=ENTITY_NAMES[resource],
            entity_id=record_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            before=before,
            after=result,
        )
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "MASTER_DATA_CONFLICT",
            "The update conflicts with existing data or references an invalid record in this company.",
        ) from exc


def archive_item(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    item_id: uuid.UUID,
) -> dict:
    before = _get_one(db, ctx, "items", item_id)

    if before["is_archived"]:
        return before

    row = db.execute(
        text(
            """UPDATE items
               SET is_archived = true, updated_at = now()
               WHERE company_id = :company_id AND id = :id
               RETURNING *"""
        ),
        {"company_id": ctx.company_id, "id": item_id},
    ).mappings().one()

    result = dict(row)
    record_audit(
        db,
        action="items.archive",
        entity_type="item",
        entity_id=item_id,
        tenant_id=ctx.tenant_id,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        request=request,
        before=before,
        after=result,
    )
    db.commit()
    return result


# ----------------------------- Unit conversions

def list_conversions(db: Session, ctx: CompanyContext) -> list[dict]:
    rows = db.execute(
        text(
            """SELECT uc.*,
                      fu.name AS from_unit_name,
                      fu.abbreviation AS from_unit_abbreviation,
                      tu.name AS to_unit_name,
                      tu.abbreviation AS to_unit_abbreviation
               FROM unit_conversions uc
               JOIN units fu ON fu.company_id = uc.company_id AND fu.id = uc.from_unit_id
               JOIN units tu ON tu.company_id = uc.company_id AND tu.id = uc.to_unit_id
               WHERE uc.company_id = :company_id
               ORDER BY fu.name, tu.name"""
        ),
        {"company_id": ctx.company_id},
    ).mappings().all()
    return [dict(row) for row in rows]


def create_conversion(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    data: dict[str, Any],
) -> dict:
    try:
        row = db.execute(
            text(
                """INSERT INTO unit_conversions
                   (company_id, from_unit_id, to_unit_id, factor)
                   VALUES (:company_id, :from_unit_id, :to_unit_id, :factor)
                   RETURNING *"""
            ),
            {"company_id": ctx.company_id, **data},
        ).mappings().one()

        result = dict(row)
        record_audit(
            db,
            action="unit_conversions.create",
            entity_type="unit_conversion",
            entity_id=result["id"],
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after=result,
        )
        db.commit()
        return result
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            409,
            "UNIT_CONVERSION_CONFLICT",
            "The units must exist in this company and the conversion pair must be unique.",
        ) from exc


def delete_conversion(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    conversion_id: uuid.UUID,
) -> None:
    before = db.execute(
        text(
            """SELECT * FROM unit_conversions
               WHERE company_id = :company_id AND id = :id"""
        ),
        {"company_id": ctx.company_id, "id": conversion_id},
    ).mappings().one_or_none()

    if before is None:
        raise AppError(404, "RECORD_NOT_FOUND", "Unit conversion not found")

    db.execute(
        text(
            """DELETE FROM unit_conversions
               WHERE company_id = :company_id AND id = :id"""
        ),
        {"company_id": ctx.company_id, "id": conversion_id},
    )

    record_audit(
        db,
        action="unit_conversions.delete",
        entity_type="unit_conversion",
        entity_id=conversion_id,
        tenant_id=ctx.tenant_id,
        company_id=ctx.company_id,
        actor_user_id=ctx.user.id,
        request=request,
        before=dict(before),
    )
    db.commit()