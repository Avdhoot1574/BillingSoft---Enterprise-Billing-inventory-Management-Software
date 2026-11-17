import uuid

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import CompanyContext
from app.core.errors import AppError
from app.modules.audit.service import record_audit


def list_stock(
    db: Session,
    ctx: CompanyContext,
    warehouse_id: uuid.UUID | None = None,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
):
    rows = db.execute(
        text("""
            SELECT
                sb.item_id,
                i.name AS item_name,
                i.sku,
                i.kind,
                sb.warehouse_id,
                w.name AS warehouse_name,
                sb.quantity_on_hand,
                sb.average_cost,
                i.reorder_level,
                (sb.quantity_on_hand * sb.average_cost) AS stock_value
            FROM stock_balances sb
            JOIN items i
              ON i.id = sb.item_id AND i.company_id = sb.company_id
            JOIN warehouses w
              ON w.id = sb.warehouse_id AND w.company_id = sb.company_id
            WHERE sb.company_id = :company_id
              AND (:warehouse_id IS NULL OR sb.warehouse_id = :warehouse_id)
              AND (:search IS NULL OR i.name ILIKE :pattern OR i.sku ILIKE :pattern)
            ORDER BY i.name, w.name
            LIMIT :limit OFFSET :offset
        """),
        {
            "company_id": ctx.company_id,
            "warehouse_id": warehouse_id,
            "search": search,
            "pattern": f"%{search}%" if search else None,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()

    return [dict(row) for row in rows]


def list_movements(
    db: Session,
    ctx: CompanyContext,
    item_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    limit: int = 100,
    offset: int = 0,
):
    rows = db.execute(
        text("""
            SELECT
                sm.*,
                i.name AS item_name,
                w.name AS warehouse_name
            FROM stock_movements sm
            JOIN items i
              ON i.id = sm.item_id AND i.company_id = sm.company_id
            JOIN warehouses w
              ON w.id = sm.warehouse_id AND w.company_id = sm.company_id
            WHERE sm.company_id = :company_id
              AND (:item_id IS NULL OR sm.item_id = :item_id)
              AND (:warehouse_id IS NULL OR sm.warehouse_id = :warehouse_id)
            ORDER BY sm.occurred_at DESC, sm.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "company_id": ctx.company_id,
            "item_id": item_id,
            "warehouse_id": warehouse_id,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()

    return [dict(row) for row in rows]


def adjust_stock(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    data: dict,
):
    try:
        quantity_delta = data["quantity_delta"]

        if quantity_delta == 0:
            raise AppError(400, "INVALID_QUANTITY",
                           "Stock adjustment quantity cannot be zero")

        item = db.execute(
            text("""
                SELECT id, track_inventory, kind
                FROM items
                WHERE id = :item_id
                  AND company_id = :company_id
                  AND is_archived = false
            """),
            {"item_id": data["item_id"], "company_id": ctx.company_id},
        ).mappings().first()

        if not item:
            raise AppError(404, "ITEM_NOT_FOUND", "Item not found")

        if not item["track_inventory"] or item["kind"] == "service":
            raise AppError(400, "INVENTORY_NOT_TRACKED",
                           "Inventory is not tracked for this item")

        warehouse = db.execute(
            text("""
                SELECT id FROM warehouses
                WHERE id = :warehouse_id
                  AND company_id = :company_id
                  AND is_active = true
            """),
            {"warehouse_id": data["warehouse_id"], "company_id": ctx.company_id},
        ).first()

        if not warehouse:
            raise AppError(404, "WAREHOUSE_NOT_FOUND",
                           "Active warehouse not found")

        balance = db.execute(
            text("""
                SELECT quantity_on_hand, average_cost
                FROM stock_balances
                WHERE company_id = :company_id
                  AND item_id = :item_id
                  AND warehouse_id = :warehouse_id
                FOR UPDATE
            """),
            {
                "company_id": ctx.company_id,
                "item_id": data["item_id"],
                "warehouse_id": data["warehouse_id"],
            },
        ).mappings().first()

        if not balance:
            db.execute(
                text("""
                    INSERT INTO stock_balances (
                        company_id, item_id, warehouse_id,
                        quantity_on_hand, average_cost
                    )
                    VALUES (:company_id, :item_id, :warehouse_id, 0, 0)
                    ON CONFLICT (company_id, item_id, warehouse_id) DO NOTHING
                """),
                {
                    "company_id": ctx.company_id,
                    "item_id": data["item_id"],
                    "warehouse_id": data["warehouse_id"],
                },
            )
            balance = db.execute(
                text("""
                    SELECT quantity_on_hand, average_cost
                    FROM stock_balances
                    WHERE company_id = :company_id
                      AND item_id = :item_id
                      AND warehouse_id = :warehouse_id
                    FOR UPDATE
                """),
                {
                    "company_id": ctx.company_id,
                    "item_id": data["item_id"],
                    "warehouse_id": data["warehouse_id"],
                },
            ).mappings().one()

        new_quantity = balance["quantity_on_hand"] + quantity_delta

        db.execute(
            text("""
                UPDATE stock_balances
                SET quantity_on_hand = :quantity,
                    average_cost = CASE
                        WHEN :quantity_delta > 0 AND :quantity > 0
                        THEN (
                            (quantity_on_hand * average_cost)
                            + (:quantity_delta * :unit_cost)
                        ) / :quantity
                        ELSE average_cost
                    END,
                    updated_at = now()
                WHERE company_id = :company_id
                  AND item_id = :item_id
                  AND warehouse_id = :warehouse_id
            """),
            {
                "quantity": new_quantity,
                "quantity_delta": quantity_delta,
                "unit_cost": data["unit_cost"],
                "company_id": ctx.company_id,
                "item_id": data["item_id"],
                "warehouse_id": data["warehouse_id"],
            },
        )

        movement_id = uuid.uuid4()

        db.execute(
            text("""
                INSERT INTO stock_movements (
                    id, company_id, item_id, warehouse_id,
                    movement_type, quantity_delta, unit_cost,
                    reference_type, reference_id, notes, created_by
                )
                VALUES (
                    :id, :company_id, :item_id, :warehouse_id,
                    'adjustment', :quantity_delta, :unit_cost,
                    'manual_adjustment', :reference_id, :notes, :created_by
                )
            """),
            {
                "id": movement_id,
                "company_id": ctx.company_id,
                "item_id": data["item_id"],
                "warehouse_id": data["warehouse_id"],
                "quantity_delta": quantity_delta,
                "unit_cost": data["unit_cost"],
                "reference_id": movement_id,
                "notes": data.get("notes"),
                "created_by": ctx.user.id,
            },
        )

        record_audit(
            db,
            action="inventory.adjusted",
            entity_type="stock_movement",
            entity_id=movement_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={
                "item_id": str(data["item_id"]),
                "warehouse_id": str(data["warehouse_id"]),
                "quantity_delta": str(quantity_delta),
            },
        )

        db.commit()

        return {
            "movement_id": movement_id,
            "item_id": data["item_id"],
            "warehouse_id": data["warehouse_id"],
            "quantity_on_hand": new_quantity,
        }

    except Exception:
        db.rollback()
        raise