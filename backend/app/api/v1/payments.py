import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.v1.payment_schemas import PaymentCreateIn
from app.core.context import CompanyContext
from app.db.session import get_db
from app.modules.payments import service


router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("", status_code=201)
def create_payment(
    body: PaymentCreateIn,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("payments.create")),
    db: Session = Depends(get_db),
):
    return service.create_payment(
        db, request, ctx, body.model_dump(mode="python")
    )


@router.get("")
def get_payments(
    direction: str | None = Query(default=None, pattern="^(in|out)$"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("payments.read")),
    db: Session = Depends(get_db),
):
    return service.list_payments(db, ctx, limit, offset, direction)


@router.get("/{payment_id}")
def get_payment(
    payment_id: uuid.UUID,
    ctx: CompanyContext = Depends(require_permission("payments.read")),
    db: Session = Depends(get_db),
):
    return service.get_payment(db, ctx, payment_id)


@router.post("/{payment_id}/reverse")
def reverse_payment(
    payment_id: uuid.UUID,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("payments.reverse")),
    db: Session = Depends(get_db),
):
    return service.reverse_payment(db, request, ctx, payment_id)