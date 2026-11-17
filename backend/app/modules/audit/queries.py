import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session


def list_audit_events(db: Session, company_id: uuid.UUID, *, limit: int, offset: int,
                      entity_type: str | None, action: str | None) -> list[dict]:
    rows = db.execute(
        text(
            """SELECT a.id, a.action, a.entity_type, a.entity_id, a.actor_user_id, u.email AS actor_email,
                      a.request_id, a.before_data, a.after_data, a.created_at
               FROM audit_events a LEFT JOIN users u ON u.id = a.actor_user_id
               WHERE a.company_id = :c
                 AND (CAST(:et AS text) IS NULL OR a.entity_type = :et)
                 AND (CAST(:ac AS text) IS NULL OR a.action = :ac)
               ORDER BY a.created_at DESC, a.id
               LIMIT :limit OFFSET :offset"""
        ),
        {"c": company_id, "et": entity_type, "ac": action, "limit": limit, "offset": offset},
    ).mappings().all()
    return [dict(r) for r in rows]
