import uuid

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.core.context import CompanyContext
from app.core.errors import AppError
from app.db.session import get_db
from app.api.v1.master_data_schemas import (
    CategoryCreate,
    CategoryUpdate,
    ItemCreate,
    ItemUpdate,
    TaxRateCreate,
    TaxRateUpdate,
    UnitConversionCreate,
    UnitCreate,
    UnitUpdate,
    WarehouseCreate,
    WarehouseUpdate,
)
from app.modules.master_data import service

router = APIRouter(tags=["master data"])


# ---------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------

@router.get("/units")
def get_units(
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("items.read")),
    db: Session = Depends(get_db),
):
    return service.list_records(db, ctx, "units", search=search, limit=limit, offset=offset)


@router.post("/units", status_code=201)
def create_unit(
    body: UnitCreate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.create")),
    db: Session = Depends(get_db),
):
    return service.create_record(db, request, ctx, "units", body.model_dump())


@router.patch("/units/{unit_id}")
def update_unit(
    unit_id: uuid.UUID,
    body: UnitUpdate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.update")),
    db: Session = Depends(get_db),
):
    return service.update_record(
        db, request, ctx, "units", unit_id, body.model_dump(exclude_unset=True)
    )


# ---------------------------------------------------------------------
# Item categories
# ---------------------------------------------------------------------

@router.get("/categories")
def get_categories(
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("items.read")),
    db: Session = Depends(get_db),
):
    return service.list_records(
        db, ctx, "categories", search=search, limit=limit, offset=offset
    )


@router.post("/categories", status_code=201)
def create_category(
    body: CategoryCreate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.create")),
    db: Session = Depends(get_db),
):
    return service.create_record(db, request, ctx, "categories", body.model_dump())


@router.patch("/categories/{category_id}")
def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.update")),
    db: Session = Depends(get_db),
):
    return service.update_record(
        db, request, ctx, "categories", category_id, body.model_dump(exclude_unset=True)
    )


# ---------------------------------------------------------------------
# Tax rates
# ---------------------------------------------------------------------

@router.get("/tax-rates")
def get_tax_rates(
    search: str | None = None,
    include_inactive: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("items.read")),
    db: Session = Depends(get_db),
):
    return service.list_records(
        db,
        ctx,
        "tax_rates",
        search=search,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )


@router.post("/tax-rates", status_code=201)
def create_tax_rate(
    body: TaxRateCreate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.create")),
    db: Session = Depends(get_db),
):
    return service.create_record(db, request, ctx, "tax_rates", body.model_dump())


@router.patch("/tax-rates/{tax_rate_id}")
def update_tax_rate(
    tax_rate_id: uuid.UUID,
    body: TaxRateUpdate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.update")),
    db: Session = Depends(get_db),
):
    return service.update_record(
        db, request, ctx, "tax_rates", tax_rate_id, body.model_dump(exclude_unset=True)
    )


# ---------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------

@router.get("/items")
def get_items(
    search: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("items.read")),
    db: Session = Depends(get_db),
):
    return service.list_records(
        db, ctx, "items", search=search, limit=limit, offset=offset
    )


@router.get("/items/{item_id}")
def get_item(
    item_id: uuid.UUID,
    ctx: CompanyContext = Depends(require_permission("items.read")),
    db: Session = Depends(get_db),
):
    item = service._get_one(db, ctx, "items", item_id)
    if item["is_archived"]:
        raise AppError(404, "RECORD_NOT_FOUND", "Item not found")
    return item


@router.post("/items", status_code=201)
def create_item(
    body: ItemCreate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.create")),
    db: Session = Depends(get_db),
):
    return service.create_record(db, request, ctx, "items", body.model_dump())


@router.patch("/items/{item_id}")
def update_item(
    item_id: uuid.UUID,
    body: ItemUpdate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.update")),
    db: Session = Depends(get_db),
):
    item = service._get_one(db, ctx, "items", item_id)
    if item["is_archived"]:
        raise AppError(404, "RECORD_NOT_FOUND", "Item not found")

    return service.update_record(
        db, request, ctx, "items", item_id, body.model_dump(exclude_unset=True)
    )


@router.post("/items/{item_id}/archive")
def archive_item(
    item_id: uuid.UUID,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("items.archive")),
    db: Session = Depends(get_db),
):
    return service.archive_item(db, request, ctx, item_id)


# ---------------------------------------------------------------------
# Unit conversions
# ---------------------------------------------------------------------

@router.get("/unit-conversions")
def get_unit_conversions(
    ctx: CompanyContext = Depends(require_permission("items.read")),
    db: Session = Depends(get_db),
):
    return service.list_conversions(db, ctx)


@router.post("/unit-conversions", status_code=201)
def create_unit_conversion(
    body: UnitConversionCreate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
):
    return service.create_conversion(db, request, ctx, body.model_dump())


@router.delete("/unit-conversions/{conversion_id}", status_code=204)
def remove_unit_conversion(
    conversion_id: uuid.UUID,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
):
    service.delete_conversion(db, request, ctx, conversion_id)
    return Response(status_code=204)


# ---------------------------------------------------------------------
# Warehouses
# ---------------------------------------------------------------------

@router.get("/warehouses")
def get_warehouses(
    search: str | None = None,
    include_inactive: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("inventory.read")),
    db: Session = Depends(get_db),
):
    return service.list_records(
        db,
        ctx,
        "warehouses",
        search=search,
        include_inactive=include_inactive,
        limit=limit,
        offset=offset,
    )


@router.post("/warehouses", status_code=201)
def create_warehouse(
    body: WarehouseCreate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
):
    return service.create_record(db, request, ctx, "warehouses", body.model_dump())


@router.patch("/warehouses/{warehouse_id}")
def update_warehouse(
    warehouse_id: uuid.UUID,
    body: WarehouseUpdate,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("inventory.adjust")),
    db: Session = Depends(get_db),
):
    return service.update_record(
        db,
        request,
        ctx,
        "warehouses",
        warehouse_id,
        body.model_dump(exclude_unset=True),
    )