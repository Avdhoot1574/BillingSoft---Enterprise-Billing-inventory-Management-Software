import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.v1.inventory_schemas import StockAdjustmentIn
from app.core.context import CompanyContext
from app.db.session import get_db
from app.modules.inventory import service


router = APIRouter(prefix="/inventory", tags=["inventory"])


@router.get("/stock")
def get_stock(
    warehouse_id: uuid.UUID | None = None,
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
):
    return service.list_stock(
        db, ctx, warehouse_id, search, limit, offset
    )


@router.get("/movements")
def get_movements(
    item_id: uuid.UUID | None = None,
    warehouse_id: uuid.UUID | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
):
    return service.list_movements(
        db, ctx, item_id, warehouse_id, limit, offset
    )


@router.post("/adjustments", status_code=201)
def create_adjustment(
    body: StockAdjustmentIn,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
):
    return service.adjust_stock(
        db, request, ctx, body.model_dump(mode="python")
    )