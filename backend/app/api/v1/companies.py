from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import get_company_context, get_current_user, require_permission
from app.api.v1.schemas import CompanyBrief, CompanyCreateIn, CompanyDetailOut, CompanyUpdateIn
from app.core.context import CompanyContext, CurrentUser
from app.db.session import get_db
from app.modules.companies import service
from app.modules.identity.service import list_my_companies

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("", response_model=list[CompanyBrief])
def my_companies(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_my_companies(db, user.id)


@router.post("", response_model=CompanyBrief, status_code=201)
def create_company(body: CompanyCreateIn, request: Request, user: CurrentUser = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return service.create_company(db, request, user=user, data=body.model_dump())


@router.get("/current", response_model=CompanyDetailOut)
def current_company(ctx: CompanyContext = Depends(get_company_context), db: Session = Depends(get_db)):
    company = service.get_company(db, ctx.company_id)
    return company | {"is_owner": ctx.is_owner, "permissions": sorted(ctx.permissions)}


@router.patch("/current", response_model=CompanyDetailOut)
def update_current_company(
    body: CompanyUpdateIn,
    request: Request,
    ctx: CompanyContext = Depends(require_permission("settings.company.manage")),
    db: Session = Depends(get_db),
):
    company = service.update_company(db, request, ctx, body.model_dump(exclude_unset=True))
    return company | {"is_owner": ctx.is_owner, "permissions": sorted(ctx.permissions)}
