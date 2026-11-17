"""schema v2: integrity fixes, ledger wiring, append-only guards

Revision ID: 0002
Revises: 0001
"""
from app.db.migrate_util import run_sql_file

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0002_v2_fixes.sql")


def downgrade() -> None:
    raise NotImplementedError("Not reversible; pre-production only. Recreate the database.")
