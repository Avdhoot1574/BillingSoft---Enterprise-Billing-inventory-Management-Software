
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.v1.party_schemas import PartyCreateIn, PartyOut, PartyUpdateIn
from app.core.context import CompanyContext
from app.db.session import get_db
from app.modules.parties import service

router = APIRouter(prefix="/parties", tags=["parties"])


@router.get("", response_model=list[PartyOut])
def list_parties(
    search: str | None = Query(default=None, max_length=200),
    kind: Literal["customer", "supplier", "both"] | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    ctx: CompanyContext = Depends(require_permission("parties.read")),
    db: Session = Depends(get_db),
):
    return service.list_parties(
        db,
        ctx,
        search=search,
        kind=kind,
        include_archived=include_archived,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=PartyOut, status_code=201)
def create_party(
    body: PartyCreateIn,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("parties.create")),
    db: Session = Depends(get_db),
):
    return service.create_party(
        db,
        request,
        ctx,
        body.model_dump(mode="python"),
    )


@router.get("/{party_id}", response_model=PartyOut)
def get_party(
    party_id: uuid.UUID,
    ctx: CompanyContext = Depends(require_permission("parties.read")),
    db: Session = Depends(get_db),
):
    return service.get_party(db, ctx, party_id)


@router.patch("/{party_id}", response_model=PartyOut)
def update_party(
    party_id: uuid.UUID,
    body: PartyUpdateIn,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("parties.update")),
    db: Session = Depends(get_db),
):
    return service.update_party(
        db,
        request,
        ctx,
        party_id,
        body.model_dump(mode="python", exclude_unset=True),
    )


@router.post("/{party_id}/archive", response_model=PartyOut)
def archive_party(
    party_id: uuid.UUID,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("parties.archive")),
    db: Session = Depends(get_db),
):
    return service.archive_party(db, request, ctx, party_id)
