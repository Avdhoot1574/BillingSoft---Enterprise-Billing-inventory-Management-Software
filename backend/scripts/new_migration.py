"""Create the next numbered migration: a .py wrapper plus an .sql file you write by hand.

Usage:  python scripts/new_migration.py add_party_tags
Then edit alembic/sql/NNNN_add_party_tags.sql and run:  alembic upgrade head
"""
import re
import sys

from _common import ROOT

VERSIONS = ROOT / "alembic" / "versions"
SQL = ROOT / "alembic" / "sql"

TEMPLATE = '''"""{title}

Revision ID: {rev}
Revises: {down}
"""
from app.db.migrate_util import run_sql_file

revision = "{rev}"
down_revision = "{down}"
branch_labels = None
depends_on = None


def upgrade() -> None:
    run_sql_file("{rev}_{slug}.sql")


def downgrade() -> None:
    run_sql_file("{rev}_{slug}.down.sql")
'''


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1
    slug = re.sub(r"[^a-z0-9]+", "_", sys.argv[1].lower()).strip("_")
    if not slug:
        print("Give the migration a name, e.g. add_party_tags")
        return 1
    numbers = [int(m.group(1)) for p in VERSIONS.glob("*.py") if (m := re.match(r"^(\d{4})_", p.name))]
    down = f"{max(numbers):04d}"
    rev = f"{max(numbers) + 1:04d}"

    (VERSIONS / f"{rev}_{slug}.py").write_text(
        TEMPLATE.format(title=slug.replace("_", " "), rev=rev, down=down, slug=slug), encoding="utf-8")
    (SQL / f"{rev}_{slug}.sql").write_text(
        f"-- {rev} {slug}\n-- Write plain PostgreSQL here (CREATE TABLE, ALTER TABLE, triggers...).\n"
        "-- It runs inside one transaction: if any statement fails, nothing is applied.\n\n", encoding="utf-8")
    (SQL / f"{rev}_{slug}.down.sql").write_text(
        f"-- Undo for {rev} (used by: alembic downgrade -1). Keep the SELECT if you do not need an undo.\nSELECT 1;\n",
        encoding="utf-8")
    print(f"Created alembic/versions/{rev}_{slug}.py")
    print(f"Created alembic/sql/{rev}_{slug}.sql      <- write your SQL here")
    print(f"Created alembic/sql/{rev}_{slug}.down.sql <- optional undo")
    print("Apply with:  alembic upgrade head")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
