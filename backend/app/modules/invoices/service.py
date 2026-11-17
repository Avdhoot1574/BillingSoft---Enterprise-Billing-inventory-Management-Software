import io
import json
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import CompanyContext
from app.core.errors import AppError
from app.modules.audit.service import record_audit

MONEY = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def _current_period_id(db: Session, company_id: uuid.UUID) -> uuid.UUID:
    row = db.execute(
        text("""
            SELECT id FROM financial_periods
            WHERE company_id = :company_id AND status = 'open'
            ORDER BY starts_on DESC LIMIT 1
        """),
        {"company_id": company_id},
    ).mappings().first()
    if not row:
        raise AppError(400, "NO_OPEN_PERIOD", "No open financial period for this company")
    return row["id"]


def next_document_number(
    db: Session, company_id: uuid.UUID, document_type: str
) -> str:
    period_id = _current_period_id(db, company_id)
    row = db.execute(
        text("""
            SELECT prefix, padding, next_number
            FROM document_sequences
            WHERE company_id = :company_id
              AND document_type = :document_type
              AND financial_period_id = :period_id
            FOR UPDATE
        """),
        {
            "company_id": company_id,
            "document_type": document_type,
            "period_id": period_id,
        },
    ).mappings().first()
    if not row:
        raise AppError(400, "NO_DOCUMENT_SEQUENCE",
                       f"No document sequence for {document_type} in this period")
    prefix = row["prefix"] or ""
    padding = row["padding"] or 0
    number = row["next_number"]
    formatted = f"{prefix}{str(number).zfill(padding)}" if padding > 0 else f"{prefix}{number}"
    db.execute(
        text("""
            UPDATE document_sequences
            SET next_number = next_number + 1, updated_at = now()
            WHERE company_id = :company_id
              AND document_type = :document_type
              AND financial_period_id = :period_id
        """),
        {
            "company_id": company_id,
            "document_type": document_type,
            "period_id": period_id,
        },
    )
    return formatted


def create_invoice(
    db: Session,
    request,
    ctx: CompanyContext,
    data: dict,
):
    try:
        if data["due_date"] and data["due_date"] < data["invoice_date"]:
            raise AppError(400, "INVALID_DUE_DATE", "Due date cannot be before invoice date")

        if data["supply_type"] not in {
            "intra_state", "inter_state", "export", "other"
        }:
            raise AppError(400, "INVALID_SUPPLY_TYPE", "Invalid supply type")

        party_id = data.get("party_id")

        if party_id:
            party = db.execute(
                text("""
                    SELECT id, name, gstin
                    FROM parties
                    WHERE id = :party_id
                      AND company_id = :company_id
                      AND is_archived = false
                """),
                {
                    "party_id": party_id,
                    "company_id": ctx.company_id,
                },
            ).mappings().first()

            if not party:
                raise AppError(404, "PARTY_NOT_FOUND", "Customer not found")

        invoice_id = uuid.uuid4()

        subtotal = Decimal(0)
        discount_total = Decimal(0)
        taxable_total = Decimal(0)
        cgst_total = Decimal(0)
        sgst_total = Decimal(0)
        igst_total = Decimal(0)
        cess_total = Decimal(0)
        prepared_lines = []

        for index, line in enumerate(data["lines"], start=1):
            quantity = Decimal(str(line["quantity"]))
            unit_price = Decimal(str(line["unit_price"]))
            discount_percent = Decimal(str(line.get("discount_percent", 0)))
            tax_rate = Decimal(str(line.get("tax_rate_percent", 0)))

            gross = money(quantity * unit_price)
            discount = money(gross * discount_percent / Decimal(100))
            taxable = money(gross - discount)

            tax = money(taxable * tax_rate / Decimal(100))

            if data["supply_type"] == "intra_state":
                cgst = money(tax / 2)
                sgst = money(tax - cgst)
                igst = Decimal(0)
            else:
                cgst = Decimal(0)
                sgst = Decimal(0)
                igst = tax

            cess = Decimal(0)
            line_total = money(taxable + cgst + sgst + igst + cess)

            subtotal += gross
            discount_total += discount
            taxable_total += taxable
            cgst_total += cgst
            sgst_total += sgst
            igst_total += igst
            cess_total += cess

            item_id = line.get("item_id")

            if item_id:
                item = db.execute(
                    text("""
                        SELECT id
                        FROM items
                        WHERE id = :item_id
                          AND company_id = :company_id
                          AND is_archived = false
                    """),
                    {
                        "item_id": item_id,
                        "company_id": ctx.company_id,
                    },
                ).first()

                if not item:
                    raise AppError(404, "ITEM_NOT_FOUND", "An invoice item was not found")

            prepared_lines.append({
                "id": uuid.uuid4(),
                "line_number": index,
                "item_id": item_id,
                "item_name": line["item_name"],
                "sku": line.get("sku"),
                "hsn_sac": line.get("hsn_sac"),
                "unit_name": line["unit_name"],
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_percent": discount_percent,
                "discount_amount": discount,
                "taxable_amount": taxable,
                "tax_rate_percent": tax_rate,
                "cgst_amount": cgst,
                "sgst_amount": sgst,
                "igst_amount": igst,
                "cess_amount": cess,
                "line_total": line_total,
                "warehouse_id": line.get("warehouse_id"),
            })

        other_charges = money(Decimal(str(data.get("other_charges", 0))))
        grand_total = money(
            taxable_total
            + cgst_total
            + sgst_total
            + igst_total
            + cess_total
            + other_charges
        )

        db.execute(
            text("""
                INSERT INTO sales_invoices (
                    id, company_id, party_id,
                    invoice_number, invoice_date, due_date,
                    status, place_of_supply_state_code, supply_type,
                    customer_name_snapshot, customer_gstin_snapshot,
                    billing_address_snapshot, shipping_address_snapshot,
                    subtotal, discount_total, taxable_total,
                    cgst_total, sgst_total, igst_total, cess_total,
                    other_charges, round_off, grand_total,
                    notes, terms, created_by
                )
                VALUES (
                    :id, :company_id, :party_id,
                    NULL, :invoice_date, :due_date,
                    'draft', :place_of_supply, :supply_type,
                    :customer_name, :customer_gstin,
                    CAST(:billing_address AS jsonb),
                    CAST(:shipping_address AS jsonb),
                    :subtotal, :discount_total, :taxable_total,
                    :cgst_total, :sgst_total, :igst_total, :cess_total,
                    :other_charges, 0, :grand_total,
                    :notes, :terms, :created_by
                )
            """),
            {
                "id": invoice_id,
                "company_id": ctx.company_id,
                "party_id": party_id,
                "invoice_date": data["invoice_date"],
                "due_date": data.get("due_date"),
                "place_of_supply": data.get("place_of_supply_state_code"),
                "supply_type": data["supply_type"],
                "customer_name": data["customer_name"],
                "customer_gstin": data.get("customer_gstin"),
                "billing_address": json.dumps(data.get("billing_address", {})),
                "shipping_address": json.dumps(data.get("shipping_address", {})),
                "subtotal": money(subtotal),
                "discount_total": money(discount_total),
                "taxable_total": money(taxable_total),
                "cgst_total": money(cgst_total),
                "sgst_total": money(sgst_total),
                "igst_total": money(igst_total),
                "cess_total": money(cess_total),
                "other_charges": other_charges,
                "grand_total": grand_total,
                "notes": data.get("notes"),
                "terms": data.get("terms"),
                "created_by": ctx.user.id,
            },
        )

        for line in prepared_lines:
            db.execute(
                text("""
                    INSERT INTO sales_invoice_lines (
                        id, company_id, invoice_id, line_number,
                        item_id, item_name_snapshot, sku_snapshot,
                        hsn_sac_snapshot, unit_name_snapshot,
                        quantity, unit_price, discount_percent,
                        discount_amount, taxable_amount, tax_rate_percent,
                        cgst_amount, sgst_amount, igst_amount,
                        cess_amount, line_total, warehouse_id
                    )
                    VALUES (
                        :id, :company_id, :invoice_id, :line_number,
                        :item_id, :item_name, :sku,
                        :hsn_sac, :unit_name,
                        :quantity, :unit_price, :discount_percent,
                        :discount_amount, :taxable_amount, :tax_rate_percent,
                        :cgst_amount, :sgst_amount, :igst_amount,
                        :cess_amount, :line_total, :warehouse_id
                    )
                """),
                {
                    **line,
                    "company_id": ctx.company_id,
                    "invoice_id": invoice_id,
                },
            )

        record_audit(
            db,
            action="invoice.created",
            entity_type="sales_invoice",
            entity_id=invoice_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"grand_total": str(grand_total), "status": "draft"},
        )

        db.commit()
        return get_invoice(db, ctx, invoice_id)

    except Exception:
        db.rollback()
        raise


def post_invoice(
    db: Session,
    request,
    ctx: CompanyContext,
    invoice_id: uuid.UUID,
):
    try:
        invoice = db.execute(
            text("""
                SELECT id, company_id, status, invoice_number, version
                FROM sales_invoices
                WHERE id = :invoice_id AND company_id = :company_id
                FOR UPDATE
            """),
            {
                "invoice_id": invoice_id,
                "company_id": ctx.company_id,
            },
        ).mappings().first()

        if not invoice:
            raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")

        if invoice["status"] != "draft":
            raise AppError(409, "INVOICE_NOT_DRAFT", "Only draft invoices can be posted")

        invoice_number = next_document_number(db, ctx.company_id, "sales_invoice")

        db.execute(
            text("""
                UPDATE sales_invoices
                SET invoice_number = :invoice_number,
                    status = 'posted',
                    posted_by = :posted_by,
                    posted_at = now(),
                    version = version + 1,
                    updated_at = now()
                WHERE id = :invoice_id AND company_id = :company_id
                  AND status = 'draft'
                  AND version = :version
            """),
            {
                "invoice_number": invoice_number,
                "posted_by": ctx.user.id,
                "invoice_id": invoice_id,
                "company_id": ctx.company_id,
                "version": invoice["version"],
            },
        )

        if db.execute(
            text("SELECT 1 FROM sales_invoices WHERE id = :id AND version = :v"),
            {"id": invoice_id, "v": invoice["version"] + 1},
        ).first() is None:
            raise AppError(409, "CONFLICT", "Invoice was modified by another user")

        record_audit(
            db,
            action="invoice.posted",
            entity_type="sales_invoice",
            entity_id=invoice_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"invoice_number": invoice_number, "status": "posted"},
        )

        db.commit()
        return get_invoice(db, ctx, invoice_id)["invoice"]
    except Exception:
        db.rollback()
        raise


def update_invoice(
    db: Session,
    request,
    ctx: CompanyContext,
    invoice_id: uuid.UUID,
    data: dict,
):
    try:
        invoice = db.execute(
            text("""
                SELECT id, status, version
                FROM sales_invoices
                WHERE id = :invoice_id AND company_id = :company_id
                FOR UPDATE
            """),
            {
                "invoice_id": invoice_id,
                "company_id": ctx.company_id,
            },
        ).mappings().first()

        if not invoice:
            raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")

        if invoice["status"] != "draft":
            raise AppError(409, "INVOICE_NOT_DRAFT", "Only draft invoices can be updated")

        if data.get("due_date") and data.get("invoice_date") and data["due_date"] < data["invoice_date"]:
            raise AppError(400, "INVALID_DUE_DATE", "Due date cannot be before invoice date")

        if data.get("supply_type") and data["supply_type"] not in {
            "intra_state", "inter_state", "export", "other"
        }:
            raise AppError(400, "INVALID_SUPPLY_TYPE", "Invalid supply type")

        party_id = data.get("party_id")
        if party_id is not None:
            party = db.execute(
                text("""
                    SELECT id FROM parties
                    WHERE id = :party_id
                      AND company_id = :company_id
                      AND is_archived = false
                """),
                {"party_id": party_id, "company_id": ctx.company_id},
            ).mappings().first()
            if not party:
                raise AppError(404, "PARTY_NOT_FOUND", "Customer not found")

        set_fields = []
        params = {"invoice_id": invoice_id, "company_id": ctx.company_id,
                  "version": invoice["version"]}

        def add(field: str, key: str, val):
            if key in data and data[key] is not None:
                set_fields.append(f"{field} = :{key}")
                params[key] = val

        add("party_id", "party_id", party_id)
        add("invoice_date", "invoice_date", data.get("invoice_date"))
        add("due_date", "due_date", data.get("due_date"))
        add("place_of_supply_state_code", "place_of_supply_state_code",
            data.get("place_of_supply_state_code"))
        add("supply_type", "supply_type", data.get("supply_type"))
        add("customer_name_snapshot", "customer_name_snapshot", data.get("customer_name"))
        add("customer_gstin_snapshot", "customer_gstin", data.get("customer_gstin"))

        if "billing_address" in data and data["billing_address"] is not None:
            set_fields.append("billing_address_snapshot = CAST(:billing_address AS jsonb)")
            params["billing_address"] = json.dumps(data["billing_address"])
        if "shipping_address" in data and data["shipping_address"] is not None:
            set_fields.append("shipping_address_snapshot = CAST(:shipping_address AS jsonb)")
            params["shipping_address"] = json.dumps(data["shipping_address"])
        add("other_charges", "other_charges", data.get("other_charges"))
        add("notes", "notes", data.get("notes"))
        add("terms", "terms", data.get("terms"))

        # Recompute lines if provided
        if "lines" in data and data["lines"] is not None:
            lines = data["lines"]
            if len(lines) < 1:
                raise AppError(400, "EMPTY_LINES", "An invoice must have at least one line")

            subtotal = Decimal(0)
            discount_total = Decimal(0)
            taxable_total = Decimal(0)
            cgst_total = Decimal(0)
            sgst_total = Decimal(0)
            igst_total = Decimal(0)
            cess_total = Decimal(0)
            prepared_lines = []

            existing = db.execute(
                text("SELECT supply_type FROM sales_invoices WHERE id = :i"),
                {"i": invoice_id},
            ).mappings().first()
            st = data.get("supply_type") or existing["supply_type"]

            for index, line in enumerate(lines, start=1):
                quantity = Decimal(str(line["quantity"]))
                unit_price = Decimal(str(line["unit_price"]))
                discount_percent = Decimal(str(line.get("discount_percent", 0)))
                tax_rate = Decimal(str(line.get("tax_rate_percent", 0)))

                gross = money(quantity * unit_price)
                discount = money(gross * discount_percent / Decimal(100))
                taxable = money(gross - discount)
                tax = money(taxable * tax_rate / Decimal(100))

                if st == "intra_state":
                    cgst = money(tax / 2)
                    sgst = money(tax - cgst)
                    igst = Decimal(0)
                else:
                    cgst = Decimal(0)
                    sgst = Decimal(0)
                    igst = tax

                cess = Decimal(0)
                line_total = money(taxable + cgst + sgst + igst + cess)

                subtotal += gross
                discount_total += discount
                taxable_total += taxable
                cgst_total += cgst
                sgst_total += sgst
                igst_total += igst
                cess_total += cess

                item_id = line.get("item_id")
                if item_id:
                    item = db.execute(
                        text("""
                            SELECT id FROM items
                            WHERE id = :item_id AND company_id = :company_id
                              AND is_archived = false
                        """),
                        {"item_id": item_id, "company_id": ctx.company_id},
                    ).first()
                    if not item:
                        raise AppError(404, "ITEM_NOT_FOUND", "An invoice item was not found")

                prepared_lines.append({
                    "id": uuid.uuid4(),
                    "line_number": index,
                    "item_id": item_id,
                    "item_name": line["item_name"],
                    "sku": line.get("sku"),
                    "hsn_sac": line.get("hsn_sac"),
                    "unit_name": line["unit_name"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "discount_percent": discount_percent,
                    "discount_amount": discount,
                    "taxable_amount": taxable,
                    "tax_rate_percent": tax_rate,
                    "cgst_amount": cgst,
                    "sgst_amount": sgst,
                    "igst_amount": igst,
                    "cess_amount": cess,
                    "line_total": line_total,
                    "warehouse_id": line.get("warehouse_id"),
                })

            other_charges_val = data.get("other_charges")
            if other_charges_val is None:
                existing_oc = db.execute(
                    text("SELECT other_charges FROM sales_invoices WHERE id = :i"),
                    {"i": invoice_id},
                ).mappings().first()
                other_charges_val = existing_oc["other_charges"]
            other_charges = money(Decimal(str(other_charges_val)))

            grand_total = money(
                taxable_total + cgst_total + sgst_total + igst_total + cess_total + other_charges
            )

            set_fields.append("subtotal = :subtotal")
            params["subtotal"] = money(subtotal)
            set_fields.append("discount_total = :discount_total")
            params["discount_total"] = money(discount_total)
            set_fields.append("taxable_total = :taxable_total")
            params["taxable_total"] = money(taxable_total)
            set_fields.append("cgst_total = :cgst_total")
            params["cgst_total"] = money(cgst_total)
            set_fields.append("sgst_total = :sgst_total")
            params["sgst_total"] = money(sgst_total)
            set_fields.append("igst_total = :igst_total")
            params["igst_total"] = money(igst_total)
            set_fields.append("cess_total = :cess_total")
            params["cess_total"] = money(cess_total)
            set_fields.append("other_charges = :other_charges")
            params["other_charges"] = other_charges
            set_fields.append("grand_total = :grand_total")
            params["grand_total"] = grand_total

            db.execute(
                text("DELETE FROM sales_invoice_lines WHERE invoice_id = :invoice_id AND company_id = :company_id"),
                {"invoice_id": invoice_id, "company_id": ctx.company_id},
            )
            for line in prepared_lines:
                db.execute(
                    text("""
                        INSERT INTO sales_invoice_lines (
                            id, company_id, invoice_id, line_number,
                            item_id, item_name_snapshot, sku_snapshot,
                            hsn_sac_snapshot, unit_name_snapshot,
                            quantity, unit_price, discount_percent,
                            discount_amount, taxable_amount, tax_rate_percent,
                            cgst_amount, sgst_amount, igst_amount,
                            cess_amount, line_total, warehouse_id
                        )
                        VALUES (
                            :id, :company_id, :invoice_id, :line_number,
                            :item_id, :item_name, :sku,
                            :hsn_sac, :unit_name,
                            :quantity, :unit_price, :discount_percent,
                            :discount_amount, :taxable_amount, :tax_rate_percent,
                            :cgst_amount, :sgst_amount, :igst_amount,
                            :cess_amount, :line_total, :warehouse_id
                        )
                    """),
                    {
                        **line,
                        "company_id": ctx.company_id,
                        "invoice_id": invoice_id,
                    },
                )

        if set_fields:
            set_fields.append("version = version + 1")
            set_fields.append("updated_at = now()")
            sql = f"""
                UPDATE sales_invoices
                SET {', '.join(set_fields)}
                WHERE id = :invoice_id AND company_id = :company_id
                  AND status = 'draft'
                  AND version = :version
            """
            result = db.execute(text(sql), params)
            if result.rowcount == 0:
                raise AppError(409, "CONFLICT", "Invoice was modified by another user")

        record_audit(
            db,
            action="invoice.updated",
            entity_type="sales_invoice",
            entity_id=invoice_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"status": "draft"},
        )

        db.commit()
        return get_invoice(db, ctx, invoice_id)

    except Exception:
        db.rollback()
        raise


def cancel_invoice(
    db: Session,
    request,
    ctx: CompanyContext,
    invoice_id: uuid.UUID,
    reason: str | None = None,
):
    try:
        invoice = db.execute(
            text("""
                SELECT id, status, version
                FROM sales_invoices
                WHERE id = :invoice_id AND company_id = :company_id
                FOR UPDATE
            """),
            {
                "invoice_id": invoice_id,
                "company_id": ctx.company_id,
            },
        ).mappings().first()

        if not invoice:
            raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")

        if invoice["status"] == "cancelled":
            raise AppError(409, "INVOICE_ALREADY_CANCELLED", "Invoice is already cancelled")

        db.execute(
            text("""
                UPDATE sales_invoices
                SET status = 'cancelled',
                    cancelled_at = now(),
                    cancellation_reason = :reason,
                    version = version + 1,
                    updated_at = now()
                WHERE id = :invoice_id AND company_id = :company_id
                  AND status <> 'cancelled'
                  AND version = :version
            """),
            {
                "reason": reason,
                "invoice_id": invoice_id,
                "company_id": ctx.company_id,
                "version": invoice["version"],
            },
        )

        if db.execute(
            text("SELECT 1 FROM sales_invoices WHERE id = :id AND version = :v"),
            {"id": invoice_id, "v": invoice["version"] + 1},
        ).first() is None:
            raise AppError(409, "CONFLICT", "Invoice was modified by another user")

        record_audit(
            db,
            action="invoice.cancelled",
            entity_type="sales_invoice",
            entity_id=invoice_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"status": "cancelled", "cancellation_reason": reason},
        )

        db.commit()
        return get_invoice(db, ctx, invoice_id)

    except Exception:
        db.rollback()
        raise


def get_invoice(db: Session, ctx: CompanyContext, invoice_id: uuid.UUID):
    invoice = db.execute(
        text("""
            SELECT *
            FROM sales_invoices
            WHERE id = :invoice_id
              AND company_id = :company_id
        """),
        {
            "invoice_id": invoice_id,
            "company_id": ctx.company_id,
        },
    ).mappings().first()

    if not invoice:
        raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")

    lines = db.execute(
        text("""
            SELECT *
            FROM sales_invoice_lines
            WHERE invoice_id = :invoice_id
              AND company_id = :company_id
            ORDER BY line_number
        """),
        {
            "invoice_id": invoice_id,
            "company_id": ctx.company_id,
        },
    ).mappings().all()

    return {"invoice": dict(invoice), "lines": [dict(line) for line in lines]}


def list_invoices(
    db: Session,
    ctx: CompanyContext,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
):
    if status is not None:
        rows = db.execute(
            text("""
                SELECT *
                FROM sales_invoices
                WHERE company_id = :company_id
                  AND status = CAST(:status AS document_status)
                ORDER BY invoice_date DESC, created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {
                "company_id": ctx.company_id,
                "status": status,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()
    else:
        rows = db.execute(
            text("""
                SELECT *
                FROM sales_invoices
                WHERE company_id = :company_id
                ORDER BY invoice_date DESC, created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {
                "company_id": ctx.company_id,
                "limit": limit,
                "offset": offset,
            },
        ).mappings().all()

    return [dict(row) for row in rows]


# ---------------------------------------------------------------- print invoice

def _money_str(value: Decimal) -> str:
    return f"{value:,.2f}"


def _date_str(value) -> str:
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return str(value)


def print_invoice(
    db: Session,
    ctx: CompanyContext,
    invoice_id: uuid.UUID,
) -> bytes:
    """Generate a print-ready PDF invoice matching the standard billing layout.

    Returns the PDF as raw bytes. Caller is responsible for setting the
    ``Content-Type: application/pdf`` response header.
    """
    result = get_invoice(db, ctx, invoice_id)
    invoice = result["invoice"]
    lines = result["lines"]

    company = db.execute(
        text("""
            SELECT name, legal_name, gstin, pan, email, phone,
                   address_line1, address_line2, city, district, state_code,
                   postal_code, country_code, currency_code
            FROM companies
            WHERE id = :company_id
        """),
        {"company_id": ctx.company_id},
    ).mappings().first()

    if not company:
        raise AppError(404, "COMPANY_NOT_FOUND", "Company not found")

    party = None
    if invoice.get("party_id"):
        party = db.execute(
            text("""
                SELECT name, gstin, email, phone
                FROM parties
                WHERE id = :party_id AND company_id = :company_id
            """),
            {"party_id": invoice["party_id"], "company_id": ctx.company_id},
        ).mappings().first()

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # ---- colours ----
    INK_DARK = HexColor("#1a2332")
    INK_MUTED = HexColor("#6b7280")
    INK_BLUE = HexColor("#1e3a8a")
    INK_LIGHT_BLUE = HexColor("#dbe7ff")
    ROW_ALT = HexColor("#f3f4f6")
    LINE_COLOR = HexColor("#e5e7eb")

    margin_l = 20 * mm
    margin_r = 20 * mm
    y = height - 15 * mm

    # ---- header: company name left, INVOICE right ----
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(INK_DARK)
    c.drawString(margin_l, y, company["name"])

    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(INK_BLUE)
    c.drawRightString(width - margin_r, y, "INVOICE")

    # company address lines below name
    c.setFont("Helvetica", 9)
    c.setFillColor(INK_MUTED)
    addr_y = y - 5 * mm
    address_lines = []
    if company.get("address_line1"):
        address_lines.append(company["address_line1"])
    if company.get("address_line2"):
        address_lines.append(company["address_line2"])
    city_line = " ".join(
        filter(None, [company.get("city"), company.get("district"), company.get("state_code"), company.get("postal_code")])
    )
    if city_line:
        address_lines.append(city_line)
    if company.get("country_code"):
        address_lines.append(company["country_code"])
    for line in address_lines:
        c.drawString(margin_l, addr_y, line)
        addr_y -= 4.5 * mm

    if company.get("gstin"):
        c.drawString(margin_l, addr_y - 2 * mm, f"GSTIN: {company['gstin']}")

    y = addr_y - 10 * mm

    # horizontal separator line
    c.setStrokeColor(LINE_COLOR)
    c.setLineWidth(0.7)
    c.line(margin_l, y, width - margin_r, y)

    # ---- invoice meta block ----
    y -= 8 * mm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(INK_DARK)
    c.drawString(margin_l, y, "Invoice#")
    c.drawRightString(width - margin_r, y, invoice.get("invoice_number") or "—")

    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.setFillColor(INK_DARK)
    c.drawString(margin_l, y, "Invoice Date")
    c.drawRightString(width - margin_r, y, _date_str(invoice.get("invoice_date")))

    y -= 6 * mm
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin_l, y, "Terms")
    c.drawRightString(width - margin_r, y, invoice.get("terms") or "Due on Receipt")

    y -= 6 * mm
    c.setFont("Helvetica", 9)
    c.drawString(margin_l, y, "Due Date")
    c.drawRightString(width - margin_r, y, _date_str(invoice.get("due_date")))

    y -= 10 * mm

    # ---- Bill To / Ship To side-by-side boxes ----
    box_w = (width - margin_l - margin_r - 10 * mm) / 2
    box_h = 25 * mm

    # Bill To box (left)
    c.setStrokeColor(LINE_COLOR)
    c.setLineWidth(0.7)
    c.setFillColor(INK_LIGHT_BLUE)
    c.roundRect(margin_l, y - box_h, box_w, box_h, 2, stroke=1, fill=1)

    c.setFillColor(INK_BLUE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin_l + 4 * mm, y - 6 * mm, "Bill To")

    c.setFillColor(INK_DARK)
    c.setFont("Helvetica", 9)
    bill_y = y - 12 * mm
    if party:
        c.drawString(margin_l + 4 * mm, bill_y, party.get("name") or "—")
        bill_y -= 5 * mm
        if party.get("gstin"):
            c.drawString(margin_l + 4 * mm, bill_y, f"GSTIN: {party['gstin']}")
            bill_y -= 5 * mm
    # Use snapshot name from invoice as fallback
    if party is None:
        c.drawString(margin_l + 4 * mm, bill_y, invoice.get("customer_name_snapshot") or "—")
        bill_y -= 5 * mm

    # address snapshot if available
    billing_addr = invoice.get("billing_address_snapshot") or {}
    if isinstance(billing_addr, dict):
        for key in ("line1", "line2", "city", "district", "state_code", "postal_code", "country_code"):
            val = billing_addr.get(key)
            if val:
                c.drawString(margin_l + 4 * mm, bill_y, str(val))
                bill_y -= 4.5 * mm

    # Ship To box (right)
    ship_x = margin_l + box_w + 10 * mm
    c.setFillColor(INK_LIGHT_BLUE)
    c.roundRect(ship_x, y - box_h, box_w, box_h, 2, stroke=1, fill=1)

    c.setFillColor(INK_BLUE)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(ship_x + 4 * mm, y - 6 * mm, "Ship To")

    c.setFillColor(INK_DARK)
    c.setFont("Helvetica", 9)
    ship_y = y - 12 * mm
    shipping_addr = invoice.get("shipping_address_snapshot") or {}
    if isinstance(shipping_addr, dict) and shipping_addr:
        if shipping_addr.get("name"):
            c.drawString(ship_x + 4 * mm, ship_y, shipping_addr["name"])
            ship_y -= 5 * mm
        for key in ("line1", "line2", "city", "district", "state_code", "postal_code", "country_code"):
            val = shipping_addr.get(key)
            if val:
                c.drawString(ship_x + 4 * mm, ship_y, str(val))
                ship_y -= 4.5 * mm
    else:
        # fall back to billing address
        if isinstance(billing_addr, dict):
            for key in ("line1", "line2", "city", "district", "state_code", "postal_code", "country_code"):
                val = billing_addr.get(key)
                if val:
                    c.drawString(ship_x + 4 * mm, ship_y, str(val))
                    ship_y -= 4.5 * mm

    y -= box_h + 12 * mm

    # ---- item table ----
    table_top = y
    col_x_num = margin_l
    col_x_item = margin_l + 12 * mm
    col_x_qty = width - margin_r - 95 * mm
    col_x_rate = width - margin_r - 65 * mm
    col_x_amt = width - margin_r - 35 * mm

    # header row
    c.setFillColor(INK_BLUE)
    c.rect(margin_l, table_top - 9 * mm, width - margin_l - margin_r, 9 * mm, stroke=0, fill=1)
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 8.5)
    c.drawString(col_x_num + 2 * mm, table_top - 7.5 * mm, "#")
    c.drawString(col_x_item + 2 * mm, table_top - 7.5 * mm, "Item & Description")
    c.drawRightString(col_x_qty + 18 * mm, table_top - 7.5 * mm, "Qty")
    c.drawRightString(col_x_rate + 30 * mm, table_top - 7.5 * mm, "Rate")
    c.drawRightString(col_x_amt + 30 * mm, table_top - 7.5 * mm, "Amount")

    c.setStrokeColor(LINE_COLOR)
    c.setLineWidth(0.5)
    c.rect(margin_l, table_top - 9 * mm, width - margin_l - margin_r, 9 * mm, stroke=1, fill=0)

    y = table_top - 18 * mm
    row_h = 8 * mm
    for idx, line in enumerate(lines, start=1):
        if idx % 2 == 0:
            c.setFillColor(ROW_ALT)
            c.rect(margin_l, y - row_h, width - margin_l - margin_r, row_h, stroke=0, fill=1)

        c.setFillColor(INK_DARK)
        c.setFont("Helvetica", 8.5)
        c.drawString(col_x_num + 2 * mm, y - 6.5 * mm, str(idx))

        item_name = line.get("item_name_snapshot") or line.get("item_name") or ""
        desc = line.get("hsn_sac_snapshot") or ""
        c.drawString(col_x_item + 2 * mm, y - 6.5 * mm, item_name)
        if desc:
            c.setFont("Helvetica", 7)
            c.setFillColor(INK_MUTED)
            c.drawString(col_x_item + 2 * mm, y - 10.5 * mm, desc)

        c.setFont("Helvetica", 8.5)
        c.setFillColor(INK_DARK)
        qty = line.get("quantity")
        rate = line.get("unit_price")
        amt = line.get("line_total")
        c.drawRightString(col_x_qty + 18 * mm, y - 6.5 * mm, _money_str(qty) if qty is not None else "0.00")
        c.drawRightString(col_x_rate + 30 * mm, y - 6.5 * mm, _money_str(rate) if rate is not None else "0.00")
        c.drawRightString(col_x_amt + 30 * mm, y - 6.5 * mm, _money_str(amt) if amt is not None else "0.00")

        c.setStrokeColor(LINE_COLOR)
        c.setLineWidth(0.3)
        c.line(margin_l, y - row_h, width - margin_r, y - row_h)

        y -= row_h

    # totals block
    totals_w = 70 * mm
    totals_x = width - margin_r - totals_w
    totals_top = y - 6 * mm

    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(INK_DARK)
    c.drawString(totals_x, totals_top, "Sub Total")
    c.drawRightString(width - margin_r, totals_top, _money_str(invoice.get("subtotal") or 0))

    totals_top -= 7 * mm
    c.setFont("Helvetica", 9)
    c.drawString(totals_x, totals_top, "Tax Rate")
    c.drawRightString(width - margin_r, totals_top, "5.00%")

    totals_top -= 7 * mm
    c.setFont("Helvetica-Bold", 10)
    c.drawString(totals_x, totals_top, "Total")
    c.drawRightString(width - margin_r, totals_top, _money_str(invoice.get("grand_total") or 0))

    totals_top -= 7 * mm
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(INK_BLUE)
    c.drawString(totals_x, totals_top, "Balance Due")
    c.drawRightString(width - margin_r, totals_top, _money_str(invoice.get("grand_total") or 0))

    y = totals_top - 14 * mm

    # ---- footer ----
    c.setFont("Helvetica-Oblique", 9)
    c.setFillColor(INK_MUTED)
    c.drawString(margin_l, y, "Thanks for shopping with us.")

    y -= 10 * mm
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(INK_DARK)
    c.drawString(margin_l, y, "Terms & Conditions")
    y -= 6 * mm
    c.setFont("Helvetica", 8)
    c.setFillColor(INK_MUTED)
    terms = invoice.get("terms") or "Full payment is due upon receipt of this invoice. Late payments may incur additional charges or interest as per the applicable laws."
    c.drawString(margin_l, y, terms)

    c.showPage()
    c.save()

    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes