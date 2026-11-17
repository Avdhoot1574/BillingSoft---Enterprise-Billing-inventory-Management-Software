"""Helpers for SQL-file based Alembic migrations.

The schema contains triggers, partial indexes and constraints that Alembic autogenerate cannot
express, so migrations are hand-written SQL files executed through the raw DBAPI cursor
(no parameter parsing, multi-statement scripts allowed, '%' is literal).
"""
from pathlib import Path

from alembic import op

SQL_DIR = Path(__file__).resolve().parents[2] / "alembic" / "sql"


def run_sql_file(name: str) -> None:
    sql = (SQL_DIR / name).read_text(encoding="utf-8")
    cursor = op.get_bind().connection.cursor()
    try:
        cursor.execute(sql)
    finally:
        cursor.close()
