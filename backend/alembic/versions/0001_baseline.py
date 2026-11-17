"""baseline schema (original project schema)

Revision ID: 0001
Revises:
"""
from app.db.migrate_util import run_sql_file

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("0001_baseline.sql")


def downgrade() -> None:
    raise NotImplementedError("Baseline is not reversible; restore from backup or recreate the database.")
