import ipaddress
import json
import uuid
from typing import Any

from fastapi import Request
from sqlalchemy import text
from sqlalchemy.orm import Session

# Keys that must never be written to the audit trail, even if a caller passes them by mistake.
_SENSITIVE = {"password", "password_hash", "token", "refresh_token", "access_token", "token_hash"}


def _clean(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    return json.dumps({k: v for k, v in data.items() if k not in _SENSITIVE}, default=str)


def _client_ip(request: Request | None) -> str | None:
    if request is None or request.client is None:
        return None
    try:
        return str(ipaddress.ip_address(request.client.host))
    except ValueError:
        return None


def record_audit(
    db: Session,
    *,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    tenant_id: uuid.UUID | None = None,
    company_id: uuid.UUID | None = None,
    actor_user_id: uuid.UUID | None = None,
    request: Request | None = None,
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> None:
    """Append an audit event inside the caller's transaction (commits/rolls back with the business change)."""
    db.execute(
        text(
            """
            INSERT INTO audit_events (tenant_id, company_id, actor_user_id, action, entity_type, entity_id,
                                      request_id, ip_address, user_agent, before_data, after_data)
            VALUES (:tenant_id, :company_id, :actor, :action, :entity_type, :entity_id,
                    :request_id, CAST(:ip AS inet), :ua, CAST(:before AS jsonb), CAST(:after AS jsonb))
            """
        ),
        {
            "tenant_id": tenant_id,
            "company_id": company_id,
            "actor": actor_user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "request_id": getattr(request.state, "request_id", None) if request else None,
            "ip": _client_ip(request),
            "ua": (request.headers.get("user-agent") or "")[:500] if request else None,
            "before": _clean(before),
            "after": _clean(after),
        },
    )
