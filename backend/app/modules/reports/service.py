from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import CompanyContext


def sales_summary(
    db: Session,
    ctx: CompanyContext,
    date_from: date,
    date_to: date,
):
    rows = db.execute(
        text("""
            SELECT
                COUNT(*) AS invoice_count,
                COALESCE(SUM(subtotal), 0) AS subtotal,
                COALESCE(SUM(discount_total), 0) AS discount_total,
                COALESCE(SUM(taxable_total), 0) AS taxable_total,
                COALESCE(SUM(cgst_total), 0) AS cgst_total,
                COALESCE(SUM(sgst_total), 0) AS sgst_total,
                COALESCE(SUM(igst_total), 0) AS igst_total,
                COALESCE(SUM(cess_total), 0) AS cess_total,
                COALESCE(SUM(other_charges), 0) AS other_charges,
                COALESCE(SUM(grand_total), 0) AS grand_total,
                COALESCE(SUM(paid_total), 0) AS paid_total
            FROM sales_invoices
            WHERE company_id = :company_id
              AND status = 'posted'
              AND invoice_date BETWEEN :date_from AND :date_to
        """),
        {
            "company_id": ctx.company_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    ).mappings().one()

    return dict(rows)


def party_sales_summary(
    db: Session,
    ctx: CompanyContext,
    date_from: date,
    date_to: date,
):
    rows = db.execute(
        text("""
            SELECT
                si.party_id,
                si.customer_name_snapshot AS party_name,
                COUNT(si.id) AS invoice_count,
                COALESCE(SUM(si.grand_total), 0) AS invoice_total,
                COALESCE(SUM(si.paid_total), 0) AS paid_total,
                COALESCE(SUM(si.grand_total - si.paid_total), 0) AS outstanding
            FROM sales_invoices si
            WHERE si.company_id = :company_id
              AND si.status = 'posted'
              AND si.invoice_date BETWEEN :date_from AND :date_to
            GROUP BY si.party_id, si.customer_name_snapshot
            ORDER BY invoice_total DESC
        """),
        {
            "company_id": ctx.company_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    ).mappings().all()

    return [dict(row) for row in rows]


def stock_summary(
    db: Session,
    ctx: CompanyContext,
    warehouse_id=None,
):
    rows = db.execute(
        text("""
            SELECT
                i.id AS item_id,
                i.name AS item_name,
                i.sku,
                w.id AS warehouse_id,
                w.name AS warehouse_name,
                sb.quantity_on_hand,
                sb.average_cost,
                sb.quantity_on_hand * sb.average_cost AS stock_value,
                i.reorder_level,
                CASE
                    WHEN sb.quantity_on_hand <= i.reorder_level THEN true
                    ELSE false
                END AS below_reorder_level
            FROM stock_balances sb
            JOIN items i
              ON i.id = sb.item_id AND i.company_id = sb.company_id
            JOIN warehouses w
              ON w.id = sb.warehouse_id AND w.company_id = sb.company_id
            WHERE sb.company_id = :company_id
              AND i.track_inventory = true
              AND (:warehouse_id IS NULL OR sb.warehouse_id = :warehouse_id)
            ORDER BY i.name, w.name
        """),
        {
            "company_id": ctx.company_id,
            "warehouse_id": warehouse_id,
        },
    ).mappings().all()

    return [dict(row) for row in rows]


def gst_summary(
    db: Session,
    ctx: CompanyContext,
    date_from: date,
    date_to: date,
):
    rows = db.execute(
        text("""
            SELECT
                supply_type,
                place_of_supply_state_code,
                COUNT(*) AS invoice_count,
                COALESCE(SUM(taxable_total), 0) AS taxable_value,
                COALESCE(SUM(cgst_total), 0) AS cgst,
                COALESCE(SUM(sgst_total), 0) AS sgst,
                COALESCE(SUM(igst_total), 0) AS igst,
                COALESCE(SUM(cess_total), 0) AS cess,
                COALESCE(SUM(grand_total), 0) AS invoice_value
            FROM sales_invoices
            WHERE company_id = :company_id
              AND status = 'posted'
              AND invoice_date BETWEEN :date_from AND :date_to
            GROUP BY supply_type, place_of_supply_state_code
            ORDER BY supply_type, place_of_supply_state_code
        """),
        {
            "company_id": ctx.company_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    ).mappings().all()

    return [dict(row) for row in rows]