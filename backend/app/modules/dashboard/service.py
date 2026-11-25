"""Live, company-scoped dashboard aggregates."""

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import CompanyContext
from app.modules.invoices.service import list_invoices


def summary(db: Session, ctx: CompanyContext) -> dict:
    result = {
        "invoice_count": None,
        "party_count": None,
        "item_count": None,
        "posted_invoice_value": None,
        "recent_invoices": None,
    }
    params = {"company_id": ctx.company_id}

    if ctx.has("sales.invoice.read"):
        row = db.execute(
            text("""SELECT count(*) AS invoice_count,
                           coalesce(sum(grand_total) FILTER (WHERE status = 'posted'), 0) AS posted_invoice_value
                    FROM sales_invoices WHERE company_id = :company_id"""),
            params,
        ).mappings().one()
        result["invoice_count"] = row["invoice_count"]
        result["posted_invoice_value"] = row["posted_invoice_value"]
        result["recent_invoices"] = list_invoices(db, ctx, limit=5)

    if ctx.has("parties.read"):
        result["party_count"] = db.execute(
            text("SELECT count(*) FROM parties WHERE company_id = :company_id AND is_archived = false"),
            params,
        ).scalar_one()

    if ctx.has("items.read"):
        result["item_count"] = db.execute(
            text("SELECT count(*) FROM items WHERE company_id = :company_id AND is_archived = false"),
            params,
        ).scalar_one()

    return result
