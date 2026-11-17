import uuid
from dataclasses import dataclass, field


@dataclass(frozen=True)
class CurrentUser:
    id: uuid.UUID
    email: str
    full_name: str
    session_id: uuid.UUID
    is_platform_admin: bool = False


@dataclass(frozen=True)
class CompanyContext:
    """Who is acting, in which tenant/company, with which permissions. Built server-side per request."""
    user: CurrentUser
    tenant_id: uuid.UUID
    company_id: uuid.UUID
    membership_id: uuid.UUID
    is_owner: bool
    permissions: frozenset[str] = field(default_factory=frozenset)

    def has(self, permission: str) -> bool:
        return permission in self.permissions
