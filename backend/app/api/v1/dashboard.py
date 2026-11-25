from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.api.deps import get_company_context
from app.core.context import CompanyContext
from app.db.session import get_db
from app.modules.dashboard.service import summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
def get_summary(
    response: Response,
    ctx: CompanyContext = Depends(get_company_context),
    db: Session = Depends(get_db),
):
    response.headers["Cache-Control"] = "no-store"
    return summary(db, ctx)
