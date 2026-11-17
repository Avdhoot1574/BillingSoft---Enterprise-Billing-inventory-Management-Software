import uuid
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import CompanyContext
from app.core.errors import AppError
from app.modules.audit.service import record_audit
from app.modules.invoices.service import next_document_number

MONEY = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def create_purchase_bill(
    db: Session,
    request,
    ctx: CompanyContext,
    data: dict,
):
    try:
        if data["due_date"] and data["due_date"] < data["bill_date"]:
            raise AppError(400, "INVALID_DUE_DATE", "Due date cannot be before bill date")

        party = db.execute(
            text("""
                SELECT id, name, gstin
                FROM parties
                WHERE id = :party_id
                  AND company_id = :company_id
                  AND is_archived = false
            """),
            {
                "party_id": data["party_id"],
                "company_id": ctx.company_id,
            },
        ).mappings().first()

        if not party:
            raise AppError(404, "PARTY_NOT_FOUND", "Supplier not found")

        bill_id = uuid.uuid4()

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
            unit_cost = Decimal(str(line["unit_cost"]))
            discount_amount = money(Decimal(str(line.get("discount_amount", 0))))
            tax_rate = Decimal(str(line.get("tax_rate_percent", 0)))

            taxable = money(quantity * unit_cost - discount_amount)
            tax = money(taxable * tax_rate / Decimal(100))

            cgst = money(tax / 2)
            sgst = money(tax - cgst)
            igst = Decimal(0)
            cess = Decimal(0)

            line_total = money(taxable + cgst + sgst + igst + cess)

            subtotal += quantity * unit_cost
            discount_total += discount_amount
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
                    raise AppError(404, "ITEM_NOT_FOUND", "A purchase bill item was not found")

            prepared_lines.append({
                "id": uuid.uuid4(),
                "line_number": index,
                "item_id": item_id,
                "item_name_snapshot": line["item_name"],
                "hsn_sac_snapshot": line.get("hsn_sac"),
                "unit_name_snapshot": line["unit_name"],
                "quantity": quantity,
                "unit_cost": unit_cost,
                "discount_amount": discount_amount,
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
            taxable_total + cgst_total + sgst_total + igst_total + cess_total + other_charges
        )

        db.execute(
            text("""
                INSERT INTO purchase_bills (
                    id, company_id, party_id,
                    bill_number, bill_date, due_date,
                    status, supplier_name_snapshot, supplier_gstin_snapshot,
                    supplier_invoice_number,
                    subtotal, discount_total, taxable_total,
                    cgst_total, sgst_total, igst_total, cess_total,
                    other_charges, round_off, grand_total,
                    notes, created_by
                )
                VALUES (
                    :id, :company_id, :party_id,
                    NULL, :bill_date, :due_date,
                    'draft', :supplier_name, :supplier_gstin,
                    :supplier_invoice_number,
                    :subtotal, :discount_total, :taxable_total,
                    :cgst_total, :sgst_total, :igst_total, :cess_total,
                    :other_charges, 0, :grand_total,
                    :notes, :created_by
                )
            """),
            {
                "id": bill_id,
                "company_id": ctx.company_id,
                "party_id": data["party_id"],
                "bill_date": data["bill_date"],
                "due_date": data.get("due_date"),
                "supplier_name": data["supplier_name_snapshot"],
                "supplier_gstin": data.get("supplier_gstin_snapshot"),
                "supplier_invoice_number": data.get("supplier_invoice_number"),
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
                "created_by": ctx.user.id,
            },
        )

        for line in prepared_lines:
            db.execute(
                text("""
                    INSERT INTO purchase_bill_lines (
                        id, company_id, purchase_bill_id, line_number,
                        item_id, item_name_snapshot, hsn_sac_snapshot,
                        unit_name_snapshot, quantity, unit_cost,
                        discount_amount, taxable_amount, tax_rate_percent,
                        cgst_amount, sgst_amount, igst_amount,
                        cess_amount, line_total, warehouse_id
                    )
                    VALUES (
                        :id, :company_id, :purchase_bill_id, :line_number,
                        :item_id, :item_name_snapshot, :hsn_sac_snapshot,
                        :unit_name_snapshot, :quantity, :unit_cost,
                        :discount_amount, :taxable_amount, :tax_rate_percent,
                        :cgst_amount, :sgst_amount, :igst_amount,
                        :cess_amount, :line_total, :warehouse_id
                    )
                """),
                {
                    **line,
                    "company_id": ctx.company_id,
                    "purchase_bill_id": bill_id,
                },
            )

        record_audit(
            db,
            action="purchase_bill.created",
            entity_type="purchase_bill",
            entity_id=bill_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"grand_total": str(grand_total), "status": "draft"},
        )

        db.commit()
        return get_purchase_bill(db, ctx, bill_id)

    except Exception:
        db.rollback()
        raise


def post_purchase_bill(
    db: Session,
    request,
    ctx: CompanyContext,
    bill_id: uuid.UUID,
):
    try:
        bill = db.execute(
            text("""
                SELECT id, company_id, status, bill_number, version
                FROM purchase_bills
                WHERE id = :bill_id AND company_id = :company_id
                FOR UPDATE
            """),
            {"bill_id": bill_id, "company_id": ctx.company_id},
        ).mappings().first()

        if not bill:
            raise AppError(404, "PURCHASE_BILL_NOT_FOUND", "Purchase bill not found")

        if bill["status"] != "draft":
            raise AppError(409, "PURCHASE_BILL_NOT_DRAFT", "Only draft purchase bills can be posted")

        bill_number = next_document_number(db, ctx.company_id, "purchase_bill")

        db.execute(
            text("""
                UPDATE purchase_bills
                SET bill_number = :bill_number,
                    status = 'posted',
                    posted_by = :posted_by,
                    posted_at = now(),
                    version = version + 1,
                    updated_at = now()
                WHERE id = :bill_id AND company_id = :company_id
                  AND status = 'draft'
                  AND version = :version
            """),
            {
                "bill_number": bill_number,
                "posted_by": ctx.user.id,
                "bill_id": bill_id,
                "company_id": ctx.company_id,
                "version": bill["version"],
            },
        )

        if db.execute(
            text("SELECT 1 FROM purchase_bills WHERE id = :id AND version = :v"),
            {"id": bill_id, "v": bill["version"]},
        ).first() is None:
            raise AppError(409, "CONFLICT", "Purchase bill was modified by another user")

        record_audit(
            db,
            action="purchase_bill.posted",
            entity_type="purchase_bill",
            entity_id=bill_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"bill_number": bill_number, "status": "posted"},
        )

        db.commit()
        return get_purchase_bill(db, ctx, bill_id)

    except Exception:
        db.rollback()
        raise


def update_purchase_bill(
    db: Session,
    request,
    ctx: CompanyContext,
    bill_id: uuid.UUID,
    data: dict,
):
    try:
        bill = db.execute(
            text("""
                SELECT id, status, version
                FROM purchase_bills
                WHERE id = :bill_id AND company_id = :company_id
                FOR UPDATE
            """),
            {"bill_id": bill_id, "company_id": ctx.company_id},
        ).mappings().first()

        if not bill:
            raise AppError(404, "PURCHASE_BILL_NOT_FOUND", "Purchase bill not found")

        if bill["status"] != "draft":
            raise AppError(409, "PURCHASE_BILL_NOT_DRAFT", "Only draft purchase bills can be updated")

        if data.get("due_date") and data.get("bill_date") and data["due_date"] < data["bill_date"]:
            raise AppError(400, "INVALID_DUE_DATE", "Due date cannot be before bill date")

        party_id = data.get("party_id")
        if party_id is not None:
            party = db.execute(
                text("""
                    SELECT id FROM parties
                    WHERE id = :party_id AND company_id = :company_id
                      AND is_archived = false
                """),
                {"party_id": party_id, "company_id": ctx.company_id},
            ).mappings().first()
            if not party:
                raise AppError(404, "PARTY_NOT_FOUND", "Supplier not found")

        set_fields = []
        params = {"bill_id": bill_id, "company_id": ctx.company_id, "version": bill["version"]}

        def add(field: str, key: str, val):
            if key in data and data[key] is not None:
                set_fields.append(f"{field} = :{key}")
                params[key] = val

        add("party_id", "party_id", party_id)
        add("bill_date", "bill_date", data.get("bill_date"))
        add("due_date", "due_date", data.get("due_date"))
        add("supplier_invoice_number", "supplier_invoice_number", data.get("supplier_invoice_number"))
        add("supplier_name_snapshot", "supplier_name_snapshot", data.get("supplier_name_snapshot"))
        add("supplier_gstin_snapshot", "supplier_gstin_snapshot", data.get("supplier_gstin_snapshot"))
        add("other_charges", "other_charges", data.get("other_charges"))
        add("notes", "notes", data.get("notes"))

        if "lines" in data and data["lines"] is not None:
            lines = data["lines"]
            if len(lines) < 1:
                raise AppError(400, "EMPTY_LINES", "A purchase bill must have at least one line")

            subtotal = Decimal(0)
            discount_total = Decimal(0)
            taxable_total = Decimal(0)
            cgst_total = Decimal(0)
            sgst_total = Decimal(0)
            igst_total = Decimal(0)
            cess_total = Decimal(0)
            prepared_lines = []

            for index, line in enumerate(lines, start=1):
                quantity = Decimal(str(line["quantity"]))
                unit_cost = Decimal(str(line["unit_cost"]))
                discount_amount = money(Decimal(str(line.get("discount_amount", 0))))
                tax_rate = Decimal(str(line.get("tax_rate_percent", 0)))

                taxable = money(quantity * unit_cost - discount_amount)
                tax = money(taxable * tax_rate / Decimal(100))

                cgst = money(tax / 2)
                sgst = money(tax - cgst)
                igst = Decimal(0)
                cess = Decimal(0)
                line_total = money(taxable + cgst + sgst + igst + cess)

                subtotal += quantity * unit_cost
                discount_total += discount_amount
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
                        raise AppError(404, "ITEM_NOT_FOUND", "A purchase bill item was not found")

                prepared_lines.append({
                    "id": uuid.uuid4(),
                    "line_number": index,
                    "item_id": item_id,
                    "item_name_snapshot": line["item_name"],
                    "hsn_sac_snapshot": line.get("hsn_sac"),
                    "unit_name_snapshot": line["unit_name"],
                    "quantity": quantity,
                    "unit_cost": unit_cost,
                    "discount_amount": discount_amount,
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
                    text("SELECT other_charges FROM purchase_bills WHERE id = :i"),
                    {"i": bill_id},
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
                text("DELETE FROM purchase_bill_lines WHERE purchase_bill_id = :bill_id AND company_id = :company_id"),
                {"bill_id": bill_id, "company_id": ctx.company_id},
            )
            for line in prepared_lines:
                db.execute(
                    text("""
                        INSERT INTO purchase_bill_lines (
                            id, company_id, purchase_bill_id, line_number,
                            item_id, item_name_snapshot, hsn_sac_snapshot,
                            unit_name_snapshot, quantity, unit_cost,
                            discount_amount, taxable_amount, tax_rate_percent,
                            cgst_amount, sgst_amount, igst_amount,
                            cess_amount, line_total, warehouse_id
                        )
                        VALUES (
                            :id, :company_id, :purchase_bill_id, :line_number,
                            :item_id, :item_name_snapshot, :hsn_sac_snapshot,
                            :unit_name_snapshot, :quantity, :unit_cost,
                            :discount_amount, :taxable_amount, :tax_rate_percent,
                            :cgst_amount, :sgst_amount, :igst_amount,
                            :cess_amount, :line_total, :warehouse_id
                        )
                    """),
                    {
                        **line,
                        "company_id": ctx.company_id,
                        "purchase_bill_id": bill_id,
                    },
                )

        if set_fields:
            set_fields.append("version = version + 1")
            set_fields.append("updated_at = now()")
            sql = f"""
                UPDATE purchase_bills
                SET {', '.join(set_fields)}
                WHERE id = :bill_id AND company_id = :company_id
                  AND status = 'draft'
                  AND version = :version
            """
            result = db.execute(text(sql), params)
            if result.rowcount == 0:
                raise AppError(409, "CONFLICT", "Purchase bill was modified by another user")

        record_audit(
            db,
            action="purchase_bill.updated",
            entity_type="purchase_bill",
            entity_id=bill_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"status": "draft"},
        )

        db.commit()
        return get_purchase_bill(db, ctx, bill_id)

    except Exception:
        db.rollback()
        raise


def cancel_purchase_bill(
    db: Session,
    request,
    ctx: CompanyContext,
    bill_id: uuid.UUID,
    reason: str | None = None,
):
    try:
        bill = db.execute(
            text("""
                SELECT id, status, version
                FROM purchase_bills
                WHERE id = :bill_id AND company_id = :company_id
                FOR UPDATE
            """),
            {"bill_id": bill_id, "company_id": ctx.company_id},
        ).mappings().first()

        if not bill:
            raise AppError(404, "PURCHASE_BILL_NOT_FOUND", "Purchase bill not found")

        if bill["status"] == "cancelled":
            raise AppError(409, "PURCHASE_BILL_ALREADY_CANCELLED", "Purchase bill is already cancelled")

        db.execute(
            text("""
                UPDATE purchase_bills
                SET status = 'cancelled',
                    cancelled_at = now(),
                    cancellation_reason = :reason,
                    version = version + 1,
                    updated_at = now()
                WHERE id = :bill_id AND company_id = :company_id
                  AND status <> 'cancelled'
                  AND version = :version
            """),
            {
                "reason": reason,
                "bill_id": bill_id,
                "company_id": ctx.company_id,
                "version": bill["version"],
            },
        )

        if db.execute(
            text("SELECT 1 FROM purchase_bills WHERE id = :id AND version = :v"),
            {"id": bill_id, "v": bill["version"]},
        ).first() is None:
            raise AppError(409, "CONFLICT", "Purchase bill was modified by another user")

        record_audit(
            db,
            action="purchase_bill.cancelled",
            entity_type="purchase_bill",
            entity_id=bill_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={"status": "cancelled", "cancellation_reason": reason},
        )

        db.commit()
        return get_purchase_bill(db, ctx, bill_id)

    except Exception:
        db.rollback()
        raise


def get_purchase_bill(db: Session, ctx: CompanyContext, bill_id: uuid.UUID):
    bill = db.execute(
        text("""
            SELECT *
            FROM purchase_bills
            WHERE id = :bill_id AND company_id = :company_id
        """),
        {"bill_id": bill_id, "company_id": ctx.company_id},
    ).mappings().first()

    if not bill:
        raise AppError(404, "PURCHASE_BILL_NOT_FOUND", "Purchase bill not found")

    lines = db.execute(
        text("""
            SELECT *
            FROM purchase_bill_lines
            WHERE purchase_bill_id = :bill_id AND company_id = :company_id
            ORDER BY line_number
        """),
        {"bill_id": bill_id, "company_id": ctx.company_id},
    ).mappings().all()

    return {"bill": dict(bill), "lines": [dict(line) for line in lines]}


def list_purchase_bills(
    db: Session,
    ctx: CompanyContext,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
):
    rows = db.execute(
        text("""
            SELECT *
            FROM purchase_bills
            WHERE company_id = :company_id
              AND (:status IS NULL OR status::text = :status)
            ORDER BY bill_date DESC, created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "company_id": ctx.company_id,
            "status": status,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()

    return [dict(row) for row in rows]