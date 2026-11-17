"""Database URL helpers shared by the helper scripts and the test suite.

Deliberately dependency-free (no SQLAlchemy / dotenv) so it can be imported before anything else.
Convention: the test database is the main database name + "_test"  (billing -> billing_test).
"""
import os
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_URL = "postgresql+psycopg://postgres:postgres@localhost:5432/billing"


def read_dotenv(path: Path | None = None) -> dict[str, str]:
    path = path or ROOT_DIR / ".env"
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def setting(name: str, default: str | None = None) -> str | None:
    """Environment variable first, then .env, then default."""
    return os.environ.get(name) or read_dotenv().get(name) or default


def database_name(url: str) -> str:
    return urlsplit(url).path.lstrip("/")


def with_database(url: str, name: str) -> str:
    return urlunsplit(urlsplit(url)._replace(path=f"/{name}"))


def main_url() -> str:
    return setting("DATABASE_URL", DEFAULT_URL)


def test_url() -> str:
    explicit = setting("TEST_DATABASE_URL")
    if explicit:
        return explicit
    url = main_url()
    return with_database(url, f"{database_name(url)}_test")


def maintenance_url(url: str) -> str:
    """Same server and credentials, but the built-in 'postgres' database (needed for CREATE DATABASE)."""
    return with_database(url, "postgres")
