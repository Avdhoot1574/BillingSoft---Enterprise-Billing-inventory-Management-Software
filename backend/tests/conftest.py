import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.urls import test_url  # noqa: E402  (dependency-free; safe to import before settings)

# Must be set before any other `app` import: settings and the DB engine are created at import time.
# Tests always run against the *_test database (see .env / TEST_DATABASE_URL), never your real data.
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = test_url()
os.environ["JWT_SECRET"] = "test-secret-test-secret-test-secret-0123456789"
os.environ["EXPOSE_INVITATION_TOKENS"] = "true"

import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

BACKEND = ROOT
TEST_URL = os.environ["DATABASE_URL"]


@pytest.fixture(scope="session", autouse=True)
def _migrated_database():
    db_name = TEST_URL.rsplit("/", 1)[-1].split("?")[0]
    if "test" not in db_name:
        raise RuntimeError(f"Refusing to wipe database '{db_name}': the test database name must contain 'test'")
    eng = create_engine(TEST_URL, isolation_level="AUTOCOMMIT")
    with eng.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    eng.dispose()

    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_URL.replace("%", "%%"))  # % is special in ini files
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _clean_tables(_migrated_database):
    yield
    from app.db.session import engine

    with engine.begin() as conn:
        # permissions (global catalogue) is intentionally kept.
        conn.execute(text("TRUNCATE users, tenants RESTART IDENTITY CASCADE"))


@pytest.fixture()
def client():
    from app.main import app

    with TestClient(app) as c:
        yield c


@pytest.fixture()
def db_engine():
    from app.db.session import engine

    return engine
