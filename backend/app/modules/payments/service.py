import uuid

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import CompanyContext
from app.core.errors import AppError
from app.modules.audit.service import record_audit
from app.modules.invoices.service import payment_status


def create_payment(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    data: dict,
):
    try:
        account = db.execute(
            text("""
                SELECT id
                FROM payment_accounts
                WHERE id = :id
                  AND company_id = :company_id
                  AND is_active = true
                FOR UPDATE
            """),
            {"id": data["payment_account_id"], "company_id": ctx.company_id},
        ).first()

        if not account:
            raise AppError(404, "PAYMENT_ACCOUNT_NOT_FOUND",
                           "Active payment account not found")

        if data.get("party_id"):
            party = db.execute(
                text("""
                    SELECT id FROM parties
                    WHERE id = :id
                      AND company_id = :company_id
                      AND is_archived = false
                """),
                {"id": data["party_id"], "company_id": ctx.company_id},
            ).first()
            if not party:
                raise AppError(404, "PARTY_NOT_FOUND", "Party not found")

        allocations = data.get("allocations", [])
        allocation_total = sum(
            (a["amount"] for a in allocations), start=0
        )

        if allocation_total > data["amount"]:
            raise AppError(400, "ALLOCATION_EXCEEDS_PAYMENT",
                           "Allocations cannot exceed the payment amount")

        payment_id = uuid.uuid4()
        payment_number = f"PAY-{uuid.uuid4().hex[:12].upper()}"

        db.execute(
            text("""
                INSERT INTO payments (
                    id, company_id, party_id, payment_account_id,
                    direction, payment_number, payment_date, amount,
                    method, reference_number, status, notes,
                    created_by, posted_at
                )
                VALUES (
                    :id, :company_id, :party_id, :account_id,
                    :direction, :payment_number, :payment_date, :amount,
                    :method, :reference_number, 'posted', :notes,
                    :created_by, now()
                )
            """),
            {
                "id": payment_id,
                "company_id": ctx.company_id,
                "party_id": data.get("party_id"),
                "account_id": data["payment_account_id"],
                "direction": data["direction"],
                "payment_number": payment_number,
                "payment_date": data["payment_date"],
                "amount": data["amount"],
                "method": data.get("method", "cash"),
                "reference_number": data.get("reference_number"),
                "notes": data.get("notes"),
                "created_by": ctx.user.id,
            },
        )

        for allocation in sorted(allocations, key=lambda a: str(a.get("sales_invoice_id") or a.get("purchase_bill_id"))):
            invoice_id = allocation.get("sales_invoice_id")
            bill_id = allocation.get("purchase_bill_id")

            if data["direction"] == "in":
                if not invoice_id or bill_id:
                    raise AppError(
                        400, "INVALID_PAYMENT_ALLOCATION",
                        "Incoming payments can only be allocated to sales invoices",
                    )

                invoice = db.execute(
                    text("""
                        SELECT id, grand_total, paid_total, party_id, status
                        FROM sales_invoices
                        WHERE id = :id AND company_id = :company_id
                        FOR UPDATE
                    """),
                    {"id": invoice_id, "company_id": ctx.company_id},
                ).mappings().first()

                if not invoice or invoice["status"] != "posted":
                    raise AppError(400, "INVALID_INVOICE",
                                   "Allocation requires a posted sales invoice")

            else:
                if not bill_id or invoice_id:
                    raise AppError(
                        400, "INVALID_PAYMENT_ALLOCATION",
                        "Outgoing payments can only be allocated to purchase bills",
                    )

                bill = db.execute(
                    text("""
                        SELECT id, grand_total, paid_total, party_id, status
                        FROM purchase_bills
                        WHERE id = :id AND company_id = :company_id
                        FOR UPDATE
                    """),
                    {"id": bill_id, "company_id": ctx.company_id},
                ).mappings().first()

                if not bill or bill["status"] != "posted":
                    raise AppError(400, "INVALID_PURCHASE_BILL",
                                   "Allocation requires a posted purchase bill")

            document = invoice if invoice_id else bill
            if document["party_id"] != data.get("party_id"):
                raise AppError(400, "PAYMENT_PARTY_MISMATCH", "Payment party must match the document party")
            table = "sales_invoices" if invoice_id else "purchase_bills"
            new_paid = document["paid_total"] + allocation["amount"]
            state = payment_status(new_paid, document["grand_total"])
            db.execute(text(f"""
                UPDATE {table} SET paid_total = :paid, payment_status = :state,
                    version = version + 1, updated_at = now()
                WHERE id = :id AND company_id = :company_id
            """), {"paid": new_paid, "state": state, "id": invoice_id or bill_id, "company_id": ctx.company_id})

            db.execute(
                text("""
                    INSERT INTO payment_allocations (
                        id, company_id, payment_id,
                        sales_invoice_id, purchase_bill_id, amount
                    )
                    VALUES (
                        :id, :company_id, :payment_id,
                        :invoice_id, :bill_id, :amount
                    )
                """),
                {
                    "id": uuid.uuid4(),
                    "company_id": ctx.company_id,
                    "payment_id": payment_id,
                    "invoice_id": invoice_id,
                    "bill_id": bill_id,
                    "amount": allocation["amount"],
                },
            )

        record_audit(
            db,
            action="payment.created",
            entity_type="payment",
            entity_id=payment_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            after={
                "payment_number": payment_number,
                "amount": str(data["amount"]),
                "direction": data["direction"],
            },
        )

        db.commit()
        return get_payment(db, ctx, payment_id)

    except Exception:
        db.rollback()
        raise


def list_payments(
    db: Session,
    ctx: CompanyContext,
    limit: int = 50,
    offset: int = 0,
    direction: str | None = None,
):
    rows = db.execute(
        text("""
            SELECT p.*, pa.name AS payment_account_name,
                   pt.name AS party_name
            FROM payments p
            JOIN payment_accounts pa
              ON pa.id = p.payment_account_id
             AND pa.company_id = p.company_id
            LEFT JOIN parties pt
              ON pt.id = p.party_id
             AND pt.company_id = p.company_id
            WHERE p.company_id = :company_id
              AND (:direction IS NULL OR p.direction::text = :direction)
            ORDER BY p.payment_date DESC, p.created_at DESC
            LIMIT :limit OFFSET :offset
        """),
        {
            "company_id": ctx.company_id,
            "direction": direction,
            "limit": limit,
            "offset": offset,
        },
    ).mappings().all()

    return [dict(row) for row in rows]


def get_payment(db: Session, ctx: CompanyContext, payment_id: uuid.UUID):
    payment = db.execute(
        text("""
            SELECT p.*, pa.name AS payment_account_name,
                   pt.name AS party_name
            FROM payments p
            JOIN payment_accounts pa
              ON pa.id = p.payment_account_id
             AND pa.company_id = p.company_id
            LEFT JOIN parties pt
              ON pt.id = p.party_id
             AND pt.company_id = p.company_id
            WHERE p.id = :id AND p.company_id = :company_id
        """),
        {"id": payment_id, "company_id": ctx.company_id},
    ).mappings().first()

    if not payment:
        raise AppError(404, "PAYMENT_NOT_FOUND", "Payment not found")

    allocations = db.execute(
        text("""
            SELECT *
            FROM payment_allocations
            WHERE payment_id = :payment_id
              AND company_id = :company_id
            ORDER BY created_at
        """),
        {"payment_id": payment_id, "company_id": ctx.company_id},
    ).mappings().all()

    return {
        "payment": dict(payment),
        "allocations": [dict(row) for row in allocations],
    }


def reverse_payment(
    db: Session,
    request: Request,
    ctx: CompanyContext,
    payment_id: uuid.UUID,
):
    try:
        payment = db.execute(
            text("""
                SELECT * FROM payments
                WHERE id = :id AND company_id = :company_id
                FOR UPDATE
            """),
            {"id": payment_id, "company_id": ctx.company_id},
        ).mappings().first()

        if not payment:
            raise AppError(404, "PAYMENT_NOT_FOUND", "Payment not found")

        if payment["status"] != "posted":
            raise AppError(409, "PAYMENT_NOT_REVERSIBLE",
                           "Only posted payments can be reversed")

        allocations = db.execute(text("""
            SELECT sales_invoice_id, purchase_bill_id, amount FROM payment_allocations
            WHERE payment_id = :id AND company_id = :company_id
        """), {"id": payment_id, "company_id": ctx.company_id}).mappings().all()
        for allocation in sorted(allocations, key=lambda a: str(a["sales_invoice_id"] or a["purchase_bill_id"])):
            table = "sales_invoices" if allocation["sales_invoice_id"] else "purchase_bills"
            doc_id = allocation["sales_invoice_id"] or allocation["purchase_bill_id"]
            params = {"id": doc_id, "company_id": ctx.company_id}
            document = db.execute(text(f"SELECT paid_total, grand_total FROM {table} WHERE id = :id AND company_id = :company_id FOR UPDATE"), params).mappings().one()
            paid = document["paid_total"] - allocation["amount"]
            state = payment_status(paid, document["grand_total"])
            db.execute(text(f"""
                UPDATE {table} SET paid_total = :paid, payment_status = :state,
                    version = version + 1, updated_at = now()
                WHERE id = :id AND company_id = :company_id
            """), {**params, "paid": paid, "state": state})

        db.execute(
            text("""
                UPDATE payments
                SET status = 'reversed'
                WHERE id = :id AND company_id = :company_id
            """),
            {"id": payment_id, "company_id": ctx.company_id},
        )

        record_audit(
            db,
            action="payment.reversed",
            entity_type="payment",
            entity_id=payment_id,
            tenant_id=ctx.tenant_id,
            company_id=ctx.company_id,
            actor_user_id=ctx.user.id,
            request=request,
            before={"status": "posted"},
            after={"status": "reversed"},
        )

        db.commit()
        return get_payment(db, ctx, payment_id)

    except Exception:
        db.rollback()
        raise