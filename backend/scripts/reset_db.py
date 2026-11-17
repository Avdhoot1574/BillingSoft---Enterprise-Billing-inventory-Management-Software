"""Development only: wipe the `billing` database and rebuild it from the migrations.

Use it when you experimented in pgAdmin and want a clean, known schema again.
Usage:  python scripts/reset_db.py
"""
from _common import alembic_config, explain_connection_error

from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from app.db.urls import database_name, main_url, setting


def main() -> int:
    if setting("APP_ENV", "dev") not in ("dev", "test"):
        print("Refusing to reset: APP_ENV is not dev/test.")
        return 1
    url = main_url()
    name = database_name(url)
    print(f"This will DELETE ALL DATA in database '{name}' and recreate every table.")
    if input(f"Type the database name ({name}) to continue: ").strip() != name:
        print("Cancelled.")
        return 1
    engine = create_engine(url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
    except OperationalError as exc:
        explain_connection_error(url, exc)
        return 1
    engine.dispose()
    command.upgrade(alembic_config(url), "head")
    print("Done. In pgAdmin right-click the database -> Refresh.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
