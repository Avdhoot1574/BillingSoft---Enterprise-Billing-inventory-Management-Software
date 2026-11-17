"""One-time setup: create .env (if missing) and the `billing` and `billing_test` databases.

Usage:  python scripts/setup_db.py
Then:   alembic upgrade head
"""
import re
import shutil

from _common import ROOT, explain_connection_error  # noqa: F401  (also fixes sys.path)

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.db.urls import database_name, main_url, maintenance_url, test_url


def main() -> int:
    env, example = ROOT / ".env", ROOT / ".env.example"
    if not env.exists():
        shutil.copy(example, env)
        print("Created .env from .env.example.")
        print("-> Open .env and put YOUR PostgreSQL password into DATABASE_URL, then run this script again.")
        return 0

    url = main_url()
    targets = [database_name(url), database_name(test_url())]
    engine = create_engine(maintenance_url(url), isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            version = conn.execute(text("SHOW server_version")).scalar_one()
            print(f"Connected. PostgreSQL {version}")
            if int(version.split(".")[0]) < 13:
                print("WARNING: PostgreSQL 13 or newer is required.")
                return 1
            for name in targets:
                if not re.fullmatch(r"[A-Za-z0-9_]+", name):
                    print(f"Refusing database name {name!r}: use letters, digits and underscores only.")
                    return 1
                exists = conn.execute(text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": name}).first()
                if exists:
                    print(f"Database '{name}' already exists.")
                else:
                    conn.execute(text(f'CREATE DATABASE "{name}"'))
                    print(f"Created database '{name}'.")
    except OperationalError as exc:
        explain_connection_error(url, exc)
        return 1
    print("\nNext:  alembic upgrade head      (then open pgAdmin -> billing -> Schemas -> public -> Tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
