"""Request dependencies: authentication, company context and permission checks.

Every business endpoint must depend on `require_permission(...)` (or at least `get_company_context`).
The company comes from the X-Company-Id header and is ALWAYS re-validated against the database:
active user membership, active tenant membership, active company. Unknown and forbidden companies
return the same 403 so IDs cannot be probed.
"""
import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.context import CompanyContext, CurrentUser
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.modules.companies.service import load_permissions

_bearer = HTTPBearer(auto_error=False)


def _unauthenticated(message: str = "Authentication required") -> AppError:
    return AppError(401, "UNAUTHENTICATED", message, headers={"WWW-Authenticate": "Bearer"})


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> CurrentUser:
    if creds is None:
        raise _unauthenticated()
    try:
        payload = decode_access_token(creds.credentials)
        user_id = uuid.UUID(payload["sub"])
        session_id = uuid.UUID(payload["sid"])
    except (jwt.PyJWTError, ValueError, KeyError):
        raise _unauthenticated("Invalid or expired token")

    row = db.execute(
        text(
            """SELECT u.id, u.email, u.full_name, u.is_platform_admin
               FROM user_sessions s JOIN users u ON u.id = s.user_id
               WHERE s.id = :sid AND s.user_id = :uid AND s.revoked_at IS NULL
                 AND s.expires_at > now() AND u.is_active"""
        ),
        {"sid": session_id, "uid": user_id},
    ).mappings().one_or_none()
    if row is None:
        raise _unauthenticated("Session is no longer valid")
    return CurrentUser(id=row["id"], email=row["email"], full_name=row["full_name"],
                       session_id=session_id, is_platform_admin=row["is_platform_admin"])


def get_company_context(
    x_company_id: str | None = Header(default=None, alias="X-Company-Id"),
    user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyContext:
    if not x_company_id:
        raise AppError(400, "COMPANY_HEADER_REQUIRED", "X-Company-Id header is required")
    try:
        company_id = uuid.UUID(x_company_id)
    except ValueError:
        raise AppError(400, "COMPANY_HEADER_INVALID", "X-Company-Id must be a UUID")

    row = db.execute(
        text(
            """SELECT cm.id AS membership_id, cm.tenant_id, cm.company_id, cm.is_owner
               FROM company_memberships cm
               JOIN companies c ON c.id = cm.company_id AND c.is_active
               JOIN tenants t ON t.id = cm.tenant_id AND t.status = 'active'
               JOIN tenant_memberships tm ON tm.tenant_id = cm.tenant_id AND tm.user_id = cm.user_id
                                         AND tm.status = 'active'
               WHERE cm.user_id = :u AND cm.company_id = :c AND cm.status = 'active'"""
        ),
        {"u": user.id, "c": company_id},
    ).mappings().one_or_none()
    if row is None:
        raise AppError(403, "COMPANY_ACCESS_DENIED", "You do not have access to this company")

    return CompanyContext(
        user=user,
        tenant_id=row["tenant_id"],
        company_id=row["company_id"],
        membership_id=row["membership_id"],
        is_owner=row["is_owner"],
        permissions=load_permissions(db, row["membership_id"], row["is_owner"]),
    )


def require_permission(permission: str) -> Callable[..., CompanyContext]:
    def dependency(ctx: CompanyContext = Depends(get_company_context)) -> CompanyContext:
        if not ctx.has(permission):
            raise AppError(403, "PERMISSION_DENIED", "You do not have permission to perform this action",
                           details={"required": permission})
        return ctx

    return dependency
