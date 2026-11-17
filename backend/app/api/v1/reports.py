from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.context import CompanyContext
from app.db.session import get_db
from app.modules.reports import service


router = APIRouter(prefix="/reports", tags=["reports"])


def validate_date_range(date_from: date, date_to: date):
    if date_to < date_from:
        from app.core.errors import AppError
        raise AppError(
            400,
            "INVALID_DATE_RANGE",
            "date_to cannot be earlier than date_from",
        )


@router.get("/sales")
def get_sales_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    ctx: CompanyContext = Depends(require_permission("reports.sales.read")),
    db: Session = Depends(get_db),
):
    validate_date_range(date_from, date_to)
    return service.sales_summary(db, ctx, date_from, date_to)


@router.get("/parties")
def get_party_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    ctx: CompanyContext = Depends(require_permission("reports.party.read")),
    db: Session = Depends(get_db),
):
    validate_date_range(date_from, date_to)
    return service.party_sales_summary(db, ctx, date_from, date_to)


@router.get("/stock")
def get_stock_report(
    warehouse_id=None,
    ctx: CompanyContext = Depends(require_permission("reports.stock.read")),
    db: Session = Depends(get_db),
):
    return service.stock_summary(db, ctx, warehouse_id)


@router.get("/gst")
def get_gst_report(
    date_from: date = Query(...),
    date_to: date = Query(...),
    ctx: CompanyContext = Depends(require_permission("reports.gst.read")),
    db: Session = Depends(get_db),
):
    validate_date_range(date_from, date_to)
    return service.gst_summary(db, ctx, date_from, date_to)