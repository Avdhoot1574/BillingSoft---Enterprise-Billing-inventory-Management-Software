"""auth: sessions, invitations, login lockout columns

Revision ID: 0003
Revises: 0002
"""
from app.db.migrate_util import run_sql_file

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0003_auth_tables.sql")


def downgrade() -> None:
    from alembic import op

    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS failed_login_count, DROP COLUMN IF EXISTS locked_until")
    op.execute("DROP TABLE IF EXISTS invitations")
    op.execute("DROP TABLE IF EXISTS user_sessions")
