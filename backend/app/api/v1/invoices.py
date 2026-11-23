import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.v1.invoice_schemas import (
    InvoiceCancel,
    InvoiceCreate,
    InvoiceOut,
    InvoiceDetailOut,
    InvoicePost,
    InvoicePaymentUpdate,
    InvoiceUpdate,
)
from app.core.context import CompanyContext
from app.core.errors import AppError
from app.db.session import get_db
from app.modules.invoices import service

router = APIRouter(prefix="/invoices", tags=["sales invoices"])


@router.get("")
def get_invoices(
    status: Literal["draft", "posted", "cancelled"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("sales.invoice.read")),
    db: Session = Depends(get_db),
):
    return service.list_invoices(db, ctx, limit, offset, status)


@router.post("", status_code=201)
def create_invoice(
    body: InvoiceCreate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("sales.invoice.create")),
    db: Session = Depends(get_db),
):
    return service.create_invoice(
        db,
        request,
        ctx,
        body.model_dump(mode="python"),
    )


@router.patch("/{invoice_id}", response_model=InvoiceOut)
def update_invoice(
    invoice_id: uuid.UUID,
    body: InvoiceUpdate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("sales.invoice.create")),
    db: Session = Depends(get_db),
):
    return service.update_invoice(
        db,
        request,
        ctx,
        invoice_id,
        body.model_dump(mode="python", exclude_unset=True),
    )


@router.post("/{invoice_id}/post", response_model=InvoiceOut)
def post_invoice(
    invoice_id: uuid.UUID,
    body: InvoicePost,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("sales.invoice.post")),
    db: Session = Depends(get_db),
):
    return service.post_invoice(db, request, ctx, invoice_id)


@router.patch("/{invoice_id}/payment", response_model=InvoiceOut)
def update_invoice_payment(
    invoice_id: uuid.UUID,
    body: InvoicePaymentUpdate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("sales.invoice.create")),
    db: Session = Depends(get_db),
):
    return service.update_invoice_payment(db, request, ctx, invoice_id, body.paid_amount)


@router.delete("/{invoice_id}")
def permanently_delete_invoice(
    invoice_id: uuid.UUID,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("sales.invoice.cancel")),
    db: Session = Depends(get_db),
):
    return service.permanently_delete_invoice(db, request, ctx, invoice_id)


@router.post("/{invoice_id}/cancel")
@router.delete("/{invoice_id}/cancel", deprecated=True)
def delete_invoice(
    invoice_id: uuid.UUID,
    body: InvoiceCancel,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("sales.invoice.cancel")),
    db: Session = Depends(get_db),
):
    if not ctx.is_owner:
        raise AppError(403, "FORBIDDEN", "Only owner can delete invoices")
    return service.delete_invoice(db, request, ctx, invoice_id, reason=body.reason)


@router.get("/{invoice_id}/print")
def print_invoice(
    invoice_id: uuid.UUID,
    ctx: CompanyContext = Depends(require_permission("sales.invoice.read")),
    db: Session = Depends(get_db),
):
    pdf_bytes = service.print_invoice(db, ctx, invoice_id)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="invoice-{invoice_id}.pdf"'
        },
    )


@router.get("/{invoice_id}", response_model=InvoiceDetailOut)
def get_invoice(
    invoice_id: uuid.UUID,
    ctx: CompanyContext = Depends(require_permission("sales.invoice.read")),
    db: Session = Depends(get_db),
):
    result = service.get_invoice(db, ctx, invoice_id)
    return {**result["invoice"], "lines": result["lines"]}
