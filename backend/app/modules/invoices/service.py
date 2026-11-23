import json
import uuid
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import CompanyContext
from app.core.errors import AppError
from app.modules.audit.service import record_audit

MONEY = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    if not value.is_finite() or abs(value) >= Decimal("1000000000000000"):
        raise AppError(400, "AMOUNT_OUT_OF_RANGE", "Amount exceeds supported monetary range")
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def payment_status(paid: Decimal, total: Decimal) -> str:
    if paid < 0 or paid > total:
        raise AppError(400, "INVALID_PAID_AMOUNT", "Paid amount must be between zero and invoice total")
    return "paid" if paid == total else "partially_paid" if paid > 0 else "unpaid"


def validate_warehouse(db, ctx, warehouse_id):
    if warehouse_id and not db.execute(text("""
        SELECT id FROM warehouses WHERE id = :id AND company_id = :company_id AND is_active = true
    """), {"id": warehouse_id, "company_id": ctx.company_id}).first():
        raise AppError(404, "WAREHOUSE_NOT_FOUND", "Active warehouse not found")


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

            validate_warehouse(db, ctx, line.get("warehouse_id"))

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
                    status, payment_status, paid_total, place_of_supply_state_code, supply_type,
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
                    'draft', :payment_status, :paid_total, :place_of_supply, :supply_type,
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
                "payment_status": payment_status(money(Decimal(str(data.get("paid_amount", 0)))), grand_total),
                "paid_total": money(Decimal(str(data.get("paid_amount", 0)))),
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
                SELECT *
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

        due_date = data.get("due_date", invoice["due_date"])
        invoice_date = data.get("invoice_date", invoice["invoice_date"])
        if due_date and due_date < invoice_date:
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
            if key in data:
                set_fields.append(f"{field} = :{key}")
                params[key] = val

        add("party_id", "party_id", party_id)
        add("invoice_date", "invoice_date", data.get("invoice_date"))
        add("due_date", "due_date", data.get("due_date"))
        add("place_of_supply_state_code", "place_of_supply_state_code",
            data.get("place_of_supply_state_code"))
        add("supply_type", "supply_type", data.get("supply_type"))
        add("customer_name_snapshot", "customer_name", data.get("customer_name"))
        add("customer_gstin_snapshot", "customer_gstin", data.get("customer_gstin"))

        if "billing_address" in data and data["billing_address"] is not None:
            set_fields.append("billing_address_snapshot = CAST(:billing_address AS jsonb)")
            params["billing_address"] = json.dumps(data["billing_address"])
        if "shipping_address" in data and data["shipping_address"] is not None:
            set_fields.append("shipping_address_snapshot = CAST(:shipping_address AS jsonb)")
            params["shipping_address"] = json.dumps(data["shipping_address"])
        add("notes", "notes", data.get("notes"))
        add("terms", "terms", data.get("terms"))
        add("paid_total", "paid_amount", data.get("paid_amount"))

        # A supply or charge change also requires recalculating stored line totals.
        if "lines" not in data and ({"supply_type", "other_charges"} & data.keys()):
            stored = get_invoice(db, ctx, invoice_id)["lines"]
            data["lines"] = [{**line, "item_name": line["item_name_snapshot"],
                              "sku": line["sku_snapshot"], "hsn_sac": line["hsn_sac_snapshot"],
                              "unit_name": line["unit_name_snapshot"]} for line in stored]

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

                validate_warehouse(db, ctx, line.get("warehouse_id"))

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
            paid_amt = money(Decimal(str(data.get("paid_amount", invoice["paid_total"]))))
            final_total = params.get("grand_total", invoice["grand_total"])
            params["payment_status"] = payment_status(paid_amt, final_total)
            set_fields.append("payment_status = :payment_status")

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
        return get_invoice(db, ctx, invoice_id)["invoice"]

    except Exception:
        db.rollback()
        raise


def update_invoice_payment(db, request, ctx, invoice_id, paid_amount):
    """Update a posted invoice's recorded balance when no payment ledger is linked."""
    try:
        invoice = db.execute(text("""
            SELECT id, status, grand_total, paid_total FROM sales_invoices
            WHERE id = :id AND company_id = :company_id FOR UPDATE
        """), {"id": invoice_id, "company_id": ctx.company_id}).mappings().first()
        if not invoice:
            raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")
        if invoice["status"] != "posted":
            raise AppError(409, "INVOICE_NOT_POSTED", "Only posted invoices can update payment here")
        linked = db.execute(text("""
            SELECT 1 FROM payment_allocations
            WHERE sales_invoice_id = :id AND company_id = :company_id LIMIT 1
        """), {"id": invoice_id, "company_id": ctx.company_id}).first()
        if linked:
            raise AppError(409, "INVOICE_HAS_ALLOCATIONS", "Reverse or record changes through the payment ledger")
        paid = money(paid_amount)
        status = payment_status(paid, invoice["grand_total"])
        db.execute(text("""
            UPDATE sales_invoices SET paid_total = :paid, payment_status = :payment_status,
                version = version + 1, updated_at = now()
            WHERE id = :id AND company_id = :company_id
        """), {"paid": paid, "payment_status": status, "id": invoice_id, "company_id": ctx.company_id})
        record_audit(db, action="invoice.payment_updated", entity_type="sales_invoice",
                     entity_id=invoice_id, tenant_id=ctx.tenant_id, company_id=ctx.company_id,
                     actor_user_id=ctx.user.id, request=request,
                     before={"paid_total": str(invoice["paid_total"])},
                     after={"paid_total": str(paid), "payment_status": status})
        db.commit()
        return get_invoice(db, ctx, invoice_id)["invoice"]
    except Exception:
        db.rollback()
        raise


def permanently_delete_invoice(db, request, ctx, invoice_id):
    if not ctx.is_owner:
        raise AppError(403, "FORBIDDEN", "Only owner can delete invoices")
    try:
        params = {"id": invoice_id, "company_id": ctx.company_id}
        invoice = db.execute(text("""
            SELECT id, invoice_number, status, paid_total FROM sales_invoices
            WHERE id = :id AND company_id = :company_id FOR UPDATE
        """), params).mappings().first()
        if not invoice:
            raise AppError(404, "INVOICE_NOT_FOUND", "Invoice not found")
        if db.execute(text("""
            SELECT 1 FROM payment_allocations WHERE sales_invoice_id = :id
              AND company_id = :company_id LIMIT 1
        """), params).first():
            raise AppError(409, "INVOICE_HAS_ALLOCATIONS", "Remove linked payment records before deleting")
        if db.execute(text("""
            SELECT 1 FROM sales_returns WHERE original_invoice_id = :id
              AND company_id = :company_id LIMIT 1
        """), params).first():
            raise AppError(409, "INVOICE_HAS_RETURNS", "Remove linked sales returns before deleting")
        db.execute(text("DELETE FROM sales_invoices WHERE id = :id AND company_id = :company_id"), params)
        record_audit(db, action="invoice.deleted", entity_type="sales_invoice",
                     entity_id=invoice_id, tenant_id=ctx.tenant_id, company_id=ctx.company_id,
                     actor_user_id=ctx.user.id, request=request,
                     before={"invoice_number": invoice["invoice_number"], "status": invoice["status"],
                             "paid_total": str(invoice["paid_total"])})
        db.commit()
        return {"id": invoice_id, "deleted": True}
    except Exception:
        db.rollback()
        raise


def delete_invoice(
    db: Session,
    request,
    ctx: CompanyContext,
    invoice_id: uuid.UUID,
    reason: str | None = None,
):
    if not ctx.is_owner:
        raise AppError(403, "FORBIDDEN", "Only owner can delete invoices")

    try:
        invoice = db.execute(
            text("""
                SELECT id, status, paid_total
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
            raise AppError(409, "INVOICE_CANCELLED", "Invoice is already cancelled")
        if invoice["paid_total"] > 0:
            raise AppError(409, "INVOICE_HAS_PAYMENTS", "Reverse payments before cancelling; clear draft payments before posting")
        db.execute(text("""
            UPDATE sales_invoices SET status = 'cancelled', cancelled_at = now(),
                cancellation_reason = :reason, version = version + 1, updated_at = now()
            WHERE id = :invoice_id AND company_id = :company_id
        """), {"invoice_id": invoice_id, "company_id": ctx.company_id, "reason": reason})

        record_audit(
            db,
            action="invoice.cancelled",
            entity_type="sales_invoice",
            entity_id=invoice_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"status": "cancelled", "reason": reason},
        )

        db.commit()
        return {"id": invoice_id, "status": "cancelled"}
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

    from app.modules.invoices.pdf import render_invoice_pdf
    return render_invoice_pdf(dict(invoice), lines, dict(company))

