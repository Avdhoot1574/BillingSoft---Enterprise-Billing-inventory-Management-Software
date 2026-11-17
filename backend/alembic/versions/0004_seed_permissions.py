"""seed the permission catalogue

Revision ID: 0004
Revises: 0003

Permissions are global rows; roles (per tenant) are created by the application when a tenant
is created. Re-running is safe (ON CONFLICT DO NOTHING). New permissions in later releases
should be added by a new migration or by app.modules.companies.service.sync_permissions().
"""
from alembic import op
import sqlalchemy as sa

from app.core.permissions import PERMISSIONS

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    for code, description in PERMISSIONS.items():
        bind.execute(
            sa.text(
                "INSERT INTO permissions (code, description) VALUES (:c, :d) ON CONFLICT (code) DO NOTHING"
            ),
            {"c": code, "d": description},
        )


def downgrade() -> None:
    pass
