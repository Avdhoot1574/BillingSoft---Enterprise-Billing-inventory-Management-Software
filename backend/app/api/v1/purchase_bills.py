import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.v1.purchase_bill_schemas import (
    PurchaseBillCancel,
    PurchaseBillCreate,
    PurchaseBillOut,
    PurchaseBillPost,
    PurchaseBillUpdate,
)
from app.core.context import CompanyContext
from app.db.session import get_db
from app.modules.purchase_bills import service

router = APIRouter(prefix="/purchase-bills", tags=["purchase bills"])


@router.get("")
def get_purchase_bills(
    status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("purchase.bill.read")),
    db: Session = Depends(get_db),
):
    return service.list_purchase_bills(db, ctx, limit, offset, status)


@router.post("", status_code=201)
def create_purchase_bill(
    body: PurchaseBillCreate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("purchase.bill.create")),
    db: Session = Depends(get_db),
):
    return service.create_purchase_bill(
        db,
        request,
        ctx,
        body.model_dump(mode="python"),
    )


@router.patch("/{bill_id}", response_model=PurchaseBillOut)
def update_purchase_bill(
    bill_id: uuid.UUID,
    body: PurchaseBillUpdate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("purchase.bill.create")),
    db: Session = Depends(get_db),
):
    return service.update_purchase_bill(
        db,
        request,
        ctx,
        bill_id,
        body.model_dump(mode="python", exclude_unset=True),
    )


@router.post("/{bill_id}/post", response_model=PurchaseBillOut)
def post_purchase_bill(
    bill_id: uuid.UUID,
    body: PurchaseBillPost,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("purchase.bill.post")),
    db: Session = Depends(get_db),
):
    return service.post_purchase_bill(db, request, ctx, bill_id)


@router.post("/{bill_id}/cancel", response_model=PurchaseBillOut)
def cancel_purchase_bill(
    bill_id: uuid.UUID,
    body: PurchaseBillCancel,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("purchase.bill.cancel")),
    db: Session = Depends(get_db),
):
    return service.cancel_purchase_bill(db, request, ctx, bill_id, reason=body.reason)


@router.get("/{bill_id}", response_model=PurchaseBillOut)
def get_purchase_bill(
    bill_id: uuid.UUID,
    ctx: CompanyContext = Depends(require_permission("purchase.bill.read")),
    db: Session = Depends(get_db),
):
    result = service.get_purchase_bill(db, ctx, bill_id)
    return result["bill"]