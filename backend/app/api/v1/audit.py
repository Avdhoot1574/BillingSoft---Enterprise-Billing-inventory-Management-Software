from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_permission
from app.api.v1.schemas import AuditEventOut
from app.core.context import CompanyContext
from app.db.session import get_db
from app.modules.audit.queries import list_audit_events

router = APIRouter(tags=["audit"])


@router.get("/audit-events", response_model=list[AuditEventOut])
def audit_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    entity_type: str | None = None,
    action: str | None = None,
    ctx: CompanyContext = Depends(require_permission("audit.read")),
    db: Session = Depends(get_db),
):
    return list_audit_events(db, ctx.company_id, limit=limit, offset=offset, entity_type=entity_type, action=action)
