import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def alembic_config(url: str):
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


def explain_connection_error(url: str, exc: Exception) -> None:
    from app.db.urls import database_name

    host = url.split("@")[-1]
    print(f"\nCould not connect to PostgreSQL ({host.split('?')[0]}).")
    print("Check that:")
    print("  1. PostgreSQL is running (Windows: Services -> postgresql-x64-NN; mac: brew services start postgresql).")
    print("  2. The user and password in DATABASE_URL (file .env) are the ones you chose when installing PostgreSQL.")
    print("     Special characters in a password must be URL-encoded (@ -> %40, : -> %3A, / -> %2F).")
    print("  3. The port is correct (default 5432; pgAdmin shows it in the server's Properties -> Connection).")
    print(f"\nOriginal error: {str(exc).strip().splitlines()[0]}")
